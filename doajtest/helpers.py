from flask_login import login_user

from unittest import TestCase
from portality import core, dao
from portality.app import app
from portality.tasks.redis_huey import main_queue, long_running
import dictdiffer
from datetime import datetime
from glob import glob
import os, csv, shutil
from portality.lib import paths
import functools
import time


def patch_config(inst, properties):
    originals = {}
    for k, v in properties.items():
        originals[k] = inst.config.get(k)
        inst.config[k] = v
    return originals


def with_es(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        obj = WithES(func)
        return obj.__call__(*args, **kwargs)
    return wrapper


class WithES:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        self.setUp()
        resp = self.func(*args, **kwargs)
        self.tearDown()
        return resp

    def setUp(self):
        core.initialise_index(app, core.es_connection)

    def tearDown(self):
        dao.DomainObject.destroy_index()


class DoajTestCase(TestCase):
    app_test = app
    originals = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.originals = patch_config(app, {
            "STORE_IMPL" : "portality.store.StoreLocal",
            "STORE_LOCAL" : paths.rel2abs(__file__, "..", "tmp", "store", "main"),
            "STORE_TMP_DIR" : paths.rel2abs(__file__, "..", "tmp", "store", "tmp"),
            "ES_RETRY_HARD_LIMIT" : 0,
            "ELASTIC_SEARCH_DB" : app.config.get('ELASTIC_SEARCH_TEST_DB'),
            'ELASTIC_SEARCH_DB_PREFIX' : core.app.config['ELASTIC_SEARCH_TEST_DB_PREFIX'],
            "FEATURES" : app.config['VALID_FEATURES'],
            'ENABLE_EMAIL' : False,
            "FAKER_SEED" : 1
        })

        main_queue.always_eager = True
        long_running.always_eager = True

        # if a test on a previous run has totally failed and tearDownClass has not run, then make sure the index is gone first
        dao.DomainObject.destroy_index()
        # time.sleep(1) # I don't know why we slept here, but not in tearDown, so I have removed it

    @classmethod
    def tearDownClass(cls) -> None:
        patch_config(app, cls.originals)
        cls.originals = {}

    def setUp(self):
        pass

    def tearDown(self):
        for f in self.list_today_article_history_files() + self.list_today_journal_history_files():
            os.remove(f)
        shutil.rmtree(paths.rel2abs(__file__, "..", "tmp"), ignore_errors=True)

    def list_today_article_history_files(self):
        return glob(os.path.join(app.config['ARTICLE_HISTORY_DIR'], datetime.now().strftime('%Y-%m-%d'), '*'))

    def list_today_journal_history_files(self):
        return glob(os.path.join(app.config['JOURNAL_HISTORY_DIR'], datetime.now().strftime('%Y-%m-%d'), '*'))

    def _make_and_push_test_context(self, path="/", acc=None):
        ctx = self.app_test.test_request_context(path)
        ctx.push()
        if acc is not None:
            # acc.save(blocking=True)
            login_user(acc)

        return ctx


def diff_dicts(d1, d2, d1_label='d1', d2_label='d2', print_unchanged=False):
    """
    Diff two dictionaries - prints changed, added and removed keys and the changed values. DOES NOT DO NESTED DICTS!

    :param d1: First dict - we compare this with d2
    :param d2: Second dict - we compare against this one
    :param d1_label: Will be used instead of "d1" in debugging output to make it more helpful.
    :param d2_label: Will be used instead of "d2" in debugging output to make it more helpful.
    :param print_unchanged: - should we print set of unchanged keys (can be long and useless). Default: False.
    :return: nothing, prints results to STDOUT
    """
    differ = dictdiffer.DictDiffer(d1, d2)
    print('Added :: keys present in {d1} which are not in {d2}'.format(d1=d1_label, d2=d2_label))
    print(differ.added())
    print()
    print('Removed :: keys present in {d2} which are not in {d1}'.format(d1=d1_label, d2=d2_label))
    print(differ.removed())
    print()
    print('Changed :: keys which are the same in {d1} and {d2} but whose values are different'.format(d1=d1_label, d2=d2_label))
    print(differ.changed())
    print()

    if differ.changed():
        print('Changed values :: the values of keys which have changed. Format is as follows:')
        print('  Key name:')
        print('    value in {d1}'.format(d1=d1_label))
        print('    value in {d2}'.format(d2=d2_label))
        print()
        for key in differ.changed():
            print(' ', key + ':')
            print('   ', d1[key])
            print('   ', d2[key])
            print()
        print()

    if print_unchanged:
        print('Unchanged :: keys which are the same in {d1} and {d2} and whose values are also the same'.format(d1=d1_label, d2=d2_label))
        print(differ.unchanged())


def load_from_matrix(filename, test_ids):
    if test_ids is None:
        test_ids = []
    with open(paths.rel2abs(__file__, "matrices", filename), 'r') as f:
        reader = csv.reader(f)
        next(reader)   # pop the header row
        cases = []
        for row in reader:
            if row[0] in test_ids or len(test_ids) == 0:
                row[0] = "row_id_" + row[0]
                cases.append(tuple(row))
        return cases


def deep_sort(obj):
    """
    Recursively sort list or dict nested lists
    """
    if isinstance(obj, dict):
        _sorted = {}
        for key in sorted(obj):
            _sorted[key] = deep_sort(obj[key])

    elif isinstance(obj, list):
        new_list = []
        for val in obj:
            new_list.append(deep_sort(val))
        _sorted = sorted(new_list)

    else:
        _sorted = obj

    return _sorted
