import datetime

def utc_ts_to_dt(ts):
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)

def dt_to_local_iso(dt):
    return dt.astimezone().strftime('%Y-%m-%d %H:%M:%S%z')

def utc_ts_to_local_iso(ts):
    return dt_to_local_iso(utc_ts_to_dt(ts))