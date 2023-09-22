from enum import IntEnum


class WPS_STATUS(IntEnum):
    UNKNOWN = 0
    ACCEPTED = 1
    STARTED = 2
    PAUSED = 3
    SUCCEEDED = 4
    FAILED = 5

