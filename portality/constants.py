# ~~Constants:Config~~
APPLICATION_STATUS_ACCEPTED = "accepted"
APPLICATION_STATUS_REJECTED = "rejected"
APPLICATION_STATUS_UPDATE_REQUEST = "update_request"
APPLICATION_STATUS_REVISIONS_REQUIRED = "revisions_required"
APPLICATION_STATUS_PENDING = "pending"
APPLICATION_STATUS_IN_PROGRESS = "in progress"
APPLICATION_STATUS_COMPLETED = "completed"
APPLICATION_STATUS_ON_HOLD = "on hold"
APPLICATION_STATUS_READY = "ready"

APPLICATION_STATUSES_ALL = [
    APPLICATION_STATUS_ACCEPTED,
    APPLICATION_STATUS_REJECTED,
    APPLICATION_STATUS_UPDATE_REQUEST,
    APPLICATION_STATUS_REVISIONS_REQUIRED,
    APPLICATION_STATUS_PENDING,
    APPLICATION_STATUS_IN_PROGRESS,
    APPLICATION_STATUS_COMPLETED,
    APPLICATION_STATUS_ON_HOLD,
    APPLICATION_STATUS_READY
]

APPLICATION_TYPE_UPDATE_REQUEST = "update_request"
APPLICATION_TYPE_NEW_APPLICATION = "new_application"

INDEX_RECORD_TYPE_UPDATE_REQUEST_UNFINISHED = "Update Request (in progress)"
INDEX_RECORD_TYPE_UPDATE_REQUEST_FINISHED = "Update Request (finished)"
INDEX_RECORD_TYPE_NEW_APPLICATION_UNFINISHED = "New Application (in progress)"
INDEX_RECORD_TYPE_NEW_APPLICATION_FINISHED = "New Application (finished)"

PROVENANCE_STATUS_REJECTED = "status:rejected"
PROVENANCE_STATUS_ACCEPTED = "status:accepted"

LOCK_APPLICATION = "suggestion"
LOCK_JOURNAL = "journal"

IDENT_TYPE_DOI = "doi"
LINK_TYPE_FULLTEXT = "fulltext"

