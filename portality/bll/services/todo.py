from portality.lib.argvalidate import argvalidate
from portality import models
from portality.bll import exceptions
from portality import constants

class TodoService(object):
    """
    ~~Todo:Service->DOAJ:Service~~
    """

    def group_stats(self, group_id):
        # ~~-> EditorGroup:Model~~
        eg = models.EditorGroup.pull(group_id)
        stats = {"editor_group" : eg.data}

        #~~-> Account:Model ~~
        stats["editors"] = {}
        editors = [eg.editor] + eg.associates
        for editor in editors:
            acc = models.Account.pull(editor)
            stats["editors"][editor] = {
                    "email" : acc.email
                }

        q = GroupStatsQuery(eg.name)
        resp = models.Application.query(q=q.query())

        stats["total"] = {"applications": 0, "update_requests": 0}

        stats["by_editor"] = {}
        for bucket in resp.get("aggregations", {}).get("editor", {}).get("buckets", []):
            stats["by_editor"][bucket["key"]] = {"applications": 0, "update_requests": 0}

            for b in bucket.get("application_type", {}).get("buckets", []):
                if b["key"] == constants.APPLICATION_TYPE_NEW_APPLICATION:
                    stats["by_editor"][bucket["key"]]["applications"] = b["doc_count"]
                    stats["total"]["applications"] += b["doc_count"]
                elif b["key"] == constants.APPLICATION_TYPE_UPDATE_REQUEST:
                    stats["by_editor"][bucket["key"]]["update_requests"] = b["doc_count"]
                    stats["total"]["update_requests"] += b["doc_count"]

        unassigned_buckets = resp.get("aggregations", {}).get("unassigned", {}).get("application_type", {}).get("buckets", [])
        stats["unassigned"] = {"applications": 0, "update_requests": 0}
        for ub in unassigned_buckets:
            if ub["key"] == constants.APPLICATION_TYPE_NEW_APPLICATION:
                stats["unassigned"]["applications"] = ub["doc_count"]
                stats["total"]["applications"] += ub["doc_count"]
            elif ub["key"] == constants.APPLICATION_TYPE_UPDATE_REQUEST:
                stats["unassigned"]["update_requests"] = ub["doc_count"]
                stats["total"]["update_requests"] += ub["doc_count"]

        stats["by_status"] = {}
        for bucket in resp.get("aggregations", {}).get("status", {}).get("buckets", []):
            stats["by_status"][bucket["key"]] = {"applications": 0, "update_requests": 0}
            for b in bucket.get("application_type", {}).get("buckets", []):
                if b["key"] == constants.APPLICATION_TYPE_NEW_APPLICATION:
                    stats["by_status"][bucket["key"]]["applications"] = b["doc_count"]
                elif b["key"] == constants.APPLICATION_TYPE_UPDATE_REQUEST:
                    stats["by_status"][bucket["key"]]["update_requests"] = b["doc_count"]

        return stats


    def top_todo(self, account, size=25):
        """
        Returns the top number of todo items for a given user

        :param account:
        :return:
        """
        # first validate the incoming arguments to ensure that we've got the right thing
        argvalidate("top_todo", [
            {"arg" : account, "instance" : models.Account, "allow_none" : False, "arg_name" : "account"}
        ], exceptions.ArgumentException)


        queries = []
        if account.has_role("admin"):
            maned_of = models.EditorGroup.groups_by_maned(account.id)
            queries.append(TodoRules.maned_stalled(size, maned_of))
            queries.append(TodoRules.maned_follow_up_old(size, maned_of))
            queries.append(TodoRules.maned_ready(size, maned_of))
            queries.append(TodoRules.maned_completed(size, maned_of))
            queries.append(TodoRules.maned_assign_pending(size, maned_of))

        todos = []
        for aid, q, sort, boost in queries:
            applications = models.Application.object_query(q=q.query())
            for ap in applications:
                todos.append({
                    "date": ap.last_manual_update_timestamp if sort == "last_manual_update" else ap.created_timestamp,
                    "date_type": sort,
                    "action_id" : [aid],
                    "title" : ap.bibjson().title,
                    "object_id" : ap.id,
                    "object" : ap,
                    "boost": boost
                })

        todos = self._rationalise_todos(todos, size)

        return todos

    def _rationalise_todos(self, todos, size):
        boosted = list(filter(lambda x: x["boost"], todos))
        unboosted = list(filter(lambda x: not x["boost"], todos))

        stds = sorted(boosted, key=lambda x: x['date']) + sorted(unboosted, key=lambda x: x['date'])

        id_map = {}
        removals = []
        for i in range(len(stds)):
            todo = stds[i]
            oid = todo["object_id"]
            if oid in id_map:
                removals.append(i)
                stds[id_map[oid]]['action_id'] += todo['action_id']
            else:
                id_map[oid] = i

        removals.reverse()
        for r in removals:
            del stds[r]

        return stds[:size]


class TodoRules(object):
    @classmethod
    def maned_stalled(cls, size, maned_of):
        stalled = TodoQuery(
            musts=[
                TodoQuery.lmu_older_than(8),
                TodoQuery.editor_group(maned_of)
            ],
            must_nots=[
                TodoQuery.status([constants.APPLICATION_STATUS_ACCEPTED, constants.APPLICATION_STATUS_REJECTED])
            ],
            sort="last_manual_update",
            size=size
        )
        return constants.TODO_MANED_STALLED, stalled, "last_manual_update", False

    @classmethod
    def maned_follow_up_old(cls, size, maned_of):
        follow_up_old = TodoQuery(
            musts=[
                TodoQuery.cd_older_than(10),
                TodoQuery.editor_group(maned_of)
            ],
            must_nots=[
                TodoQuery.status([constants.APPLICATION_STATUS_ACCEPTED, constants.APPLICATION_STATUS_REJECTED])
            ],
            sort="created_date",
            size=size
        )
        return constants.TODO_MANED_FOLLOW_UP_OLD, follow_up_old, "created_date", False

    @classmethod
    def maned_ready(cls, size, maned_of):
        ready = TodoQuery(
            musts=[
                TodoQuery.status([constants.APPLICATION_STATUS_READY]),
                TodoQuery.editor_group(maned_of)
            ],
            sort="last_manual_update",
            size=size
        )
        return constants.TODO_MANED_READY, ready, "last_manual_update", True

    @classmethod
    def maned_completed(cls, size, maned_of):
        completed = TodoQuery(
            musts=[
                TodoQuery.status([constants.APPLICATION_STATUS_COMPLETED]),
                TodoQuery.lmu_older_than(2),
                TodoQuery.editor_group(maned_of)
            ],
            sort="last_manual_update",
            size=size
        )
        return constants.TODO_MANED_COMPLETED, completed, "last_manual_update", False

    @classmethod
    def maned_assign_pending(cls, size, maned_of):
        assign_pending = TodoQuery(
            musts=[
                TodoQuery.exists("admin.editor_group"),
                TodoQuery.lmu_older_than(2),
                TodoQuery.status([constants.APPLICATION_STATUS_PENDING]),
                TodoQuery.editor_group(maned_of)
            ],
            must_nots=[
                TodoQuery.exists("admin.editor")
            ],
            sort="created_date",
            size=size
        )
        return constants.TODO_MANED_ASSIGN_PENDING, assign_pending, "last_manual_update", False


class TodoQuery(object):
    """
    ~~->$Todo:Query~~
    ~~^->Elasticsearch:Technology~~
    """
    lmu_sort = {"last_manual_update" : {"order" : "asc"}}
    cd_sort = {"created_date" : {"order" : "asc"}}

    def __init__(self, musts=None, must_nots=None, sort="last_manual_update", size=10):
        self._musts = [] if musts is None else musts
        self._must_nots = [] if must_nots is None else must_nots
        self._sort = sort
        self._size = size

    def query(self):
        sort = self.lmu_sort if self._sort == "last_manual_update" else self.cd_sort
        q = {
            "query" : {
                "bool" : {
                    "must": self._musts,
                    "must_not": self._must_nots
                }
            },
            "sort" : [
                sort
            ],
            "size" : self._size
        }
        return q

    @classmethod
    def editor_group(cls, groups):
        return {
            "terms" : {
                "admin.editor_group.exact" : [g.name for g in groups]
            }
        }

    @classmethod
    def lmu_older_than(cls, weeks):
        return {
            "range": {
                "last_manual_update": {
                    "lte": "now-" + str(weeks) + "w"
                }
            }
        }

    @classmethod
    def cd_older_than(cls, weeks):
        return {
            "range": {
                "created_date": {
                    "lte": "now-" + str(weeks) + "w"
                }
            }
        }

    @classmethod
    def status(cls, statuses):
        return {
            "terms" : {
                "admin.application_status.exact" : statuses
            }
        }

    @classmethod
    def exists(cls, field):
        return {
            "exists" : {
                "field" : field
            }
        }


class GroupStatsQuery():
    """
    ~~->$GroupStats:Query~~
    ~~^->Elasticsearch:Technology~~
    """
    def __init__(self, group_name, editor_count=10):
        self.group_name = group_name
        self.editor_count = editor_count

    def query(self):
        return {
            "track_total_hits" : True,
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "admin.editor_group.exact": self.group_name
                            }
                        }
                    ],
                    "must_not" : [
                        {
                            "terms" : {
                                "admin.application_status.exact" : [
                                    constants.APPLICATION_STATUS_ACCEPTED,
                                    constants.APPLICATION_STATUS_REJECTED
                                ]
                            }
                        }
                    ]
                }
            },
            "size" : 0,
            "aggs" : {
                "editor" : {
                    "terms" : {
                        "field" : "admin.editor.exact",
                        "size" : self.editor_count
                    },
                    "aggs" : {
                        "application_type" : {
                            "terms" : {
                                "field": "admin.application_type.exact",
                                "size": 2
                            }
                        }
                    }
                },
                "status" : {
                    "terms" : {
                        "field" : "admin.application_status.exact",
                        "size" : len(constants.APPLICATION_STATUSES_ALL)
                    },
                    "aggs": {
                        "application_type": {
                            "terms": {
                                "field": "admin.application_type.exact",
                                "size": 2
                            }
                        }
                    }
                },
                "unassigned" : {
                    "missing" : {
                        "field": "admin.editor.exact"
                    },
                    "aggs" : {
                        "application_type" : {
                            "terms" : {
                                "field": "admin.application_type.exact",
                                "size": 2
                            }
                        }
                    }
                }
            }
        }