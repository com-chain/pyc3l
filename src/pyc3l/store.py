# -*- coding: utf-8 -*-

import pickle
import sqlite3
import os
from collections import defaultdict

from . import common


def range_remove(target_range, current_block_ranges):
    """Return the ranges (s, e) of missing blocks in the range [start, end]

    >>> range_remove((1, 10), [(1, 5), (7, 12)])
    [(6, 6)]
    >>> range_remove((1, 10), [(0, 3), (7, 8)])
    [(4, 6), (9, 10)]
    >>> range_remove((1, 10), [(0, 10)])
    []
    >>> range_remove((1, 10), [(6, 6)])
    [(1, 5), (7, 10)]

    """
    (start, end) = target_range
    ## find missing blocks
    missing_block_ranges = []
    for s, e in current_block_ranges:
        if e < start:
            continue
        if start < s:
            if end < s:
                missing_block_ranges.append((start, end))
                return missing_block_ranges
            ## start < s <= end
            missing_block_ranges.append((start, s - 1))
            if e > end:
                return missing_block_ranges
            ## start < s <= e <= end
            start = e + 1
            continue
        ## s <= start <= e
        start = e + 1
        continue
    if start <= end:
        missing_block_ranges.append((start, end))
    return missing_block_ranges


def range_union(*ranges):
    """Return the smallest range union of the given ranges

    >>> range_union()
    []
    >>> range_union((1, 5))
    [(1, 5)]
    >>> range_union((1, 5), (7, 10))
    [(1, 5), (7, 10)]
    >>> range_union((1, 5), (6, 10))
    [(1, 10)]
    >>> range_union((1, 5), (3, 10))
    [(1, 10)]
    >>> range_union((1, 5), (5, 7))
    [(1, 7)]
    >>> range_union((1, 5), (6, 7))
    [(1, 7)]


    """
    ranges = sorted(ranges)
    union = []
    if not ranges:
        return union
    (start, end) = ranges[0]
    for s, e in ranges[1:]:
        if e < start:
            continue
        if s <= end + 1:
            end = max(end, e)
            continue
        union.append((start, end))
        (start, end) = (s, e)
    union.append((start, end))
    return union


def range_intersection(*ranges):
    """Return the smallest range intersection of the given ranges

    >>> range_intersection()
    []
    >>> range_intersection((1, 5))
    [(1, 5)]
    >>> range_intersection((1, 5), (7, 10))
    []
    >>> range_intersection((1, 5), (6, 10))
    []
    >>> range_intersection((1, 5), (3, 10))
    [(3, 5)]
    >>> range_intersection((1, 5), (5, 7))
    [(5, 5)]
    >>> range_intersection((1, 5), (6, 7))
    []

    """
    ranges = sorted(ranges)
    intersection = []
    if len(ranges) == 0:
        return intersection
    if len(ranges) == 1:
        return ranges
    (start, end) = ranges[0]
    for s, e in ranges[1:]:
        if e < start:
            continue
        if s <= end:
            intersection.append((max(start, s), min(end, e)))
            (start, end) = (max(start, s), min(end, e))
    return intersection


def ranges_intersection_2(ranges1, ranges2):
    """Return the smallest range intersection of the given ranges

    >>> ranges_intersection_2([(1, 5)], [(1, 5)])
    [(1, 5)]
    >>> ranges_intersection_2([(1, 5)], [(6, 10)])
    []
    >>> ranges_intersection_2([(1, 5)], [(3, 10)])
    [(3, 5)]
    >>> ranges_intersection_2([(1, 5)], [(5, 7)])
    [(5, 5)]
    >>> ranges_intersection_2([(1, 5)], [(6, 7)])
    []
    >>> ranges_intersection_2([], [(6, 7)])
    []
    >>> ranges_intersection_2([], [])
    []
    >>> ranges_intersection_2([(1, 5), (7, 10)], [(3, 10)])
    [(3, 5), (7, 10)]

    """
    intersection = []
    for r1 in ranges1:
        for r2 in ranges2:
            if r1[1] < r2[0] or r1[0] > r2[1]:
                continue
            intersection.append((max(r1[0], r2[0]), min(r1[1], r2[1])))
    return intersection


def ranges_intersection(*ranges):
    """Return the smallest range intersection of the given ranges

    >>> ranges_intersection([(1, 5), (7, 10)], [(3, 10)], [(2, 6)])
    [(3, 5)]
    >>> ranges_intersection([(1, 5), (7, 10)], [(3, 10)], [(5, 8)], [(1, 10)])
    [(5, 5), (7, 8)]
    >>> ranges_intersection()
    []
    >>> ranges_intersection([(1, 5)])
    [(1, 5)]
    >>> ranges_intersection([(1, 5)], [(7, 10)])
    []

    """
    if not ranges:
        return []
    intersection = ranges[0]
    for r in ranges[1:]:
        intersection = ranges_intersection_2(intersection, r)
    return intersection


def curate_block_date(block_dates, ranges):
    """Return the block-date dict curated for the given ranges

    It will remove all key/value where the key is not in one of
    the boundary of a range.

    >>> curate_block_date({}, [])
    {}
    >>> curate_block_date({}, [(1, 3), (5, 5)])
    {}
    >>> curate_block_date({1: 1}, [(1, 3), (5, 5)])
    {1: 1}
    >>> curate_block_date({2: 2}, [(1, 3), (5, 5)])
    {}
    >>> curate_block_date({3: 3}, [(1, 3), (5, 5)])
    {3: 3}
    >>> curate_block_date({4: 4}, [(1, 3), (5, 5)])
    {}
    >>> curate_block_date({5: 5}, [(1, 3), (5, 5)])
    {5: 5}
    >>> curate_block_date({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, [(1, 3), (5, 5)])
    {1: 1, 3: 3, 5: 5}
    >>> curate_block_date({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, [(2, 2), (3, 5)])
    {2: 2, 3: 3, 5: 5}
    >>> curate_block_date({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, [(1, 1), (2, 2), (3, 5)])
    {1: 1, 2: 2, 3: 3, 5: 5}

    """
    def walk_block_date_iter():
        wbri = walk_block_range_iter()
        try:
            r = next(wbri)
        except StopIteration:
            return
        for b, d in sorted(block_dates.items()):
            while True:
                if b in r:
                    yield b, d
                    break
                if b < r[1]:
                    break
                try:
                    r = wbri.send(b)
                except StopIteration:
                    break

    def walk_block_range_iter():
        b = 0
        for r in ranges:
            if b > r[1]:
                continue
            # if b < r[0]:
            #     break
            b = yield r

    return dict(walk_block_date_iter())


class TxStore:
    def __init__(self, pyc3l, currency, safe_wallet_add):
        self.pyc3l = pyc3l
        self.inited = False
        self.currency = currency
        self._current_ranges = None
        self._current_block_dates = None
        self._sqlite3_conn = None
        self._sqlite3_cursor = None
        self._sqlite3_transaction_started = False
        self._safe_wallet_add = safe_wallet_add

    def _init(self):
        if not self.inited:
            PYC3L_CACHE_DIR = common.init_cache_dirs()

            self.cache_tx_db_state = os.path.join(
                PYC3L_CACHE_DIR, f"tx_db_{self.currency}_state"
            )  ## pickled state
            self.cache_block_dates_state = os.path.join(
                PYC3L_CACHE_DIR, f"block_db_{self.currency}_state"
            )  ## pickled state
            self.cache_tx_db = os.path.join(
                PYC3L_CACHE_DIR, f"tx_db_{self.currency}.sqlite"
            )  ## sqlite db

            ## init if not exists

            self._sqlite3_conn = sqlite3.connect(self.cache_tx_db)
            self._sqlite3_conn.row_factory = sqlite3.Row
            self._sqlite3_cursor = self._sqlite3_conn.cursor()
            self.init_db()
        self.inited = True

    def execute(self, *args):
        """Enforce transactionality of sqlite3 execute

        an explicit commit is required to effectively apply previous
        changes.
        """
        if not self._sqlite3_transaction_started:
            self._sqlite3_cursor.execute("BEGIN TRANSACTION")
            self._sqlite3_transaction_started = True
        self._sqlite3_cursor.execute(*args)

    def commit(self):
        """Commit the transaction to the database"""
        self._sqlite3_conn.commit()
        self._sqlite3_transaction_started = False

    def _create_db(self):
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                hash text NOT NULL UNIQUE,
                block integer,
                received_at integer,
                caller text,
                contract text,
                contract_abi text,
                fn text,
                fn_abi text,
                type text,
                sender text,
                receiver text,
                amount integer,
                status text
            )
        """
        )
        self.commit()

    def init_db(self):
        self._create_db()

    def current_ranges(self):
        """Return the ranges (s, e) of fullfilled blocks"""
        if self._current_ranges is None:
            self._init()
            ## load current block from pickled state file
            if os.path.exists(self.cache_tx_db_state):
                self._current_ranges = pickle.load(open(self.cache_tx_db_state, "rb"))
            else:
                self._current_ranges = []
        return self._current_ranges

    def has_block(self, block_number):
        """Return True if the block is in the current ranges"""
        return any(s <= block_number <= e for s, e in self.current_ranges())

    @property
    def current_block_dates(self):
        if self._current_block_dates is None:
            self._init()
            ## get block-date cache
            if os.path.exists(self.cache_block_dates_state):
                self._current_block_dates = pickle.load(open(self.cache_block_dates_state, "rb"))
            else:
                self._current_block_dates = {}
        return self._current_block_dates

    def add_block(self, block_number, collated_ts):
        """Add a block to the current ranges"""

        ## update block range cache

        self._current_ranges = range_union(
            (block_number, block_number), *self.current_ranges()
        )

        pickle.dump(self._current_ranges, open(self.cache_tx_db_state, "wb"))


        ## update block-date cache

        self.current_block_dates[block_number] = collated_ts
        self._current_block_dates = curate_block_date(self.current_block_dates, self.current_ranges())

        pickle.dump(self.current_block_dates, open(self.cache_block_dates_state, "wb"))

    def add_tx(self, data):
        """Add a transaction to the database"""
        self._init()
        self.execute(
                """
            INSERT INTO transactions VALUES (
                :hash, :block, :received_at, :caller, :contract, :contract_abi,
                :fn, :fn_abi, :type, :sender, :receiver, :amount, :status
            )
        """,
        data,
            )


    def _record_sql(self, granularity="%Y-%m"):


        self._init()
        if self._safe_wallet_add is None:
            query = """
                SELECT
                    strftime(?, received_at, 'unixepoch') AS month,
                    SUM(CASE WHEN type = 'pledge' THEN amount ELSE 0 END)/100.0 AS pledge_total,
                    COUNT(CASE WHEN type = 'pledge' THEN 1 ELSE NULL END) AS pledge_nb,
                    SUM(CASE WHEN type = 'transfer' THEN amount ELSE 0 END)/100.0 AS transfer_total,
                    COUNT(CASE WHEN type = 'transfer' THEN 1 ELSE NULL END) AS transfer_nb,
                    0.0 AS reconv_total,
                    0 AS reconv_nb
                FROM
                    transactions
                GROUP BY
                    month
                ORDER BY
                    month;
            """
            params = [granularity]
        else:

            params = [granularity]
            safe_wallets_sql = f"({','.join(['?' for _ in self._safe_wallet_add])})"
            is_topup_sql = f"(type = 'pledge' AND receiver NOT IN {safe_wallets_sql})"
            is_topup_sql += " OR "
            is_topup_sql += f"(type = 'transfer' AND sender IN {safe_wallets_sql})"

            is_transfer_sql = f"(type = 'transfer' AND sender NOT IN {safe_wallets_sql}"
            is_transfer_sql += f" AND receiver NOT IN {safe_wallets_sql})"

            is_reconv_sql = f"(type = 'transfer' AND receiver IN {safe_wallets_sql})"

            params += 10 * list(self._safe_wallet_add)

            query = f"""
                SELECT
                    strftime(?, received_at, 'unixepoch') AS month,
                    SUM(CASE WHEN {is_topup_sql} THEN amount ELSE 0 END)/100.0 AS pledge_total,
                    COUNT(CASE WHEN {is_topup_sql} THEN 1 ELSE NULL END) AS pledge_nb,
                    SUM(CASE WHEN {is_transfer_sql} THEN amount ELSE 0 END)/100.0 AS transfer_total,
                    COUNT(CASE WHEN {is_transfer_sql} THEN 1 ELSE NULL END) AS transfer_nb,
                    SUM(CASE WHEN {is_reconv_sql} THEN amount ELSE 0 END)/100.0 AS reconv_total,
                    COUNT(CASE WHEN {is_reconv_sql} THEN 1 ELSE NULL END) AS reconv_nb
                FROM
                    transactions
                GROUP BY
                    month
                ORDER BY
                    month;
            """

        cursor = self._sqlite3_conn.cursor()

        cursor.execute(query, params)

        for row in cursor:
            month = row[0]
            total_pledge = row[1] or 0.0
            nb_pledge = row[2] or 0
            total_transfer = row[3] or 0.0
            nb_transfer = row[4] or 0
            total_reconv = row[5] or 0.0
            nb_reconv = row[6] or 0

            pledge_minus_reconv = total_pledge - total_reconv
            ## correct float rounding errors:
            pledge_minus_reconv = round(pledge_minus_reconv, 2)
            yield (month, total_pledge, nb_pledge,
                   total_transfer, nb_transfer, total_reconv,
                   nb_reconv, pledge_minus_reconv)

    def records(self, granularity="%Y-%m",
                start_date=None,
                end_date=None,
                address_groups=None,
                pledge_group="national currency"):

        params = [granularity]
        where_clauses = []
        if start_date is not None:
            start_date = start_date.timestamp
            where_clauses.append("received_at >= ?")
            params.append(start_date)
        if end_date is not None:
            end_date = end_date.timestamp
            where_clauses.append("received_at <= ?")
            params.append(end_date)

        where_clause = ""
        if len(where_clauses) > 0:
            where_clause = "WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT
                strftime(?, received_at, 'unixepoch') AS group_unit,
                type, receiver, sender, amount
            FROM
                transactions
            {where_clause}
            ORDER BY
                group_unit;
        """

        cursor = self._sqlite3_conn.cursor()
        cursor.execute(query, params)

        ## reverse the dict to resolve addresses to group
        addresses = {}
        for group, addrs in address_groups.items():
            for addr in addrs:
                addresses[addr] = group

        try:
            tx = next(cursor)
        except StopIteration:
            return

        def mk_new_matrix():
            return defaultdict(lambda: defaultdict(lambda: {"total": 0, "nb": 0}))

        prev_group_unit = tx["group_unit"]
        current_matrix = mk_new_matrix()

        def consolidate_matrix(matrix, tx):
            ## resolve groups
            group_sender = pledge_group if tx["type"] == "pledge" else addresses.get(tx["sender"])
            group_receiver = addresses.get(tx["receiver"])
            ## Accumulate amount in matrix
            matrix[group_sender][group_receiver]["total"] += tx["amount"]
            matrix[group_sender][group_receiver]["nb"] += 1

        consolidate_matrix(current_matrix, tx)

        for tx in cursor:
            if tx["group_unit"] != prev_group_unit:
                yield (prev_group_unit, current_matrix)
                current_matrix = mk_new_matrix()
                prev_group_unit = tx["group_unit"]

            if tx["type"] in ("pledge", "transfer"):
                consolidate_matrix(current_matrix, tx)

        yield (tx["group_unit"], current_matrix)
