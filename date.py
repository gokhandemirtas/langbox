import fuzzydate as fd
from datetime import datetime

dat = fd.to_datetime("next tuesday 2pm")
formatted = datetime.strftime(dat, "%Y-%m-%d")
print(dat)
print(formatted)
