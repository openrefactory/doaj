from doajtest.helpers import DoajTestCase
from portality.lib.dataobj import DataObj
from portality.api.v1.data_objects import JournalDO
from portality import models
from datetime import datetime
from doajtest.fixtures import ApplicationFixtureFactory, JournalFixtureFactory, ArticleFixtureFactory
import time

class TestAPIDataObj(DoajTestCase):

    # we aren't going to talk to ES so override setup and teardown of index
    def setUp(self):
        self.jm = models.Journal(**JournalFixtureFactory.make_journal_source())

    def tearDown(self):
        pass

    def test_01_create_empty(self):
        """Create an empty dataobject, mostly to check it doesn't die a recursive death"""
        do = DataObj()
        assert do.data == {}
        assert do._struct is None
        with self.assertRaises(AttributeError):
            do.nonexistent_attribute

    def test_02_create_from_dict(self):
        expected_struct = JournalFixtureFactory.make_journal_apido_struct()
        do = DataObj(raw=self.jm.data, struct=expected_struct, construct_silent_prune=True, expose_data=True)
        assert do._struct == expected_struct
        self.check_do(do, expected_struct)

    def test_03_create_from_model(self):
        expected_struct = JournalFixtureFactory.make_journal_apido_struct()
        do = JournalDO.from_model(self.jm)
        assert do._struct == expected_struct
        self.check_do(do, expected_struct)

    def check_do(self, do, expected_struct):
        assert isinstance(do.admin, DataObj), 'Declared as "object" but not a Data Object?'
        assert do.id == self.jm.id
        assert do.created_date == self.jm.created_date
        assert do.last_updated == self.jm.last_updated

        assert isinstance(do.admin.contact, list), 'Declared as "list" but is not a list?'
        assert len(do.admin.contact) == 1
        assert isinstance(do.admin.contact[0], DataObj), 'Declared as "object" but not a Data Object?'
        assert do.admin.contact[0].name == self.jm.get_latest_contact_name()
        assert do.admin.contact[0].email == self.jm.get_latest_contact_email()
        assert do.admin.in_doaj is self.jm.is_in_doaj(), 'actual val {0} is of type {1}'.format(do.admin.in_doaj, type(do.admin.in_doaj))
        assert do.admin.ticked is self.jm.is_ticked()  # it's not set in the journal fixture so we expect a None back
        assert do.admin.seal is self.jm.has_seal()
        assert do.admin.owner == self.jm.owner

        assert isinstance(do.bibjson, DataObj), 'Declared as "object" but not a Data Object?'
        assert do.bibjson.title == self.jm.bibjson().title
        assert do.bibjson.alternative_title == self.jm.bibjson().alternative_title
        assert do.bibjson.country == self.jm.bibjson().country
        assert do.bibjson.publisher == self.jm.bibjson().publisher
        assert do.bibjson.provider == self.jm.bibjson().provider
        assert do.bibjson.institution == self.jm.bibjson().institution
        assert do.bibjson.apc_url == self.jm.bibjson().apc_url
        assert do.bibjson.submission_charges_url == self.jm.bibjson().submission_charges_url
        assert do.bibjson.allows_fulltext_indexing == self.jm.bibjson().allows_fulltext_indexing
        assert do.bibjson.publication_time == self.jm.bibjson().publication_time

        for o in expected_struct['structs']['bibjson']['objects']:
            assert isinstance(getattr(do.bibjson, o), DataObj), '{0} declared as "object" but not a Data Object?'.format(o)

        for l in expected_struct['structs']['bibjson']['lists']:
            assert isinstance(getattr(do.bibjson, l), list), '{0} declared as "list" but not a list?'.format(l)

        assert do.bibjson.oa_start.year == self.jm.bibjson().oa_start.get('year')
        assert do.bibjson.oa_start.volume == self.jm.bibjson().oa_start.get('volume')
        assert do.bibjson.oa_start.number == self.jm.bibjson().oa_start.get('number')

        assert do.bibjson.oa_end.year == self.jm.bibjson().oa_end.get('year')
        assert do.bibjson.oa_end.volume == self.jm.bibjson().oa_end.get('volume')
        assert do.bibjson.oa_end.number == self.jm.bibjson().oa_end.get('number')

        assert do.bibjson.apc.currency == self.jm.bibjson().apc['currency']
        assert do.bibjson.apc.average_price == self.jm.bibjson().apc['average_price']
        assert do.bibjson.submission_charges.currency == self.jm.bibjson().submission_charges['currency']
        assert do.bibjson.submission_charges.average_price == self.jm.bibjson().submission_charges['average_price']

        assert do.bibjson.archiving_policy.url == self.jm.bibjson().archiving_policy['url']
        assert isinstance(do.bibjson.archiving_policy.policy, list)
        # TODO the below line passes but journal struct needs enhancing here
        # assert do.bibjson.archiving_policy.policy == [u"['LOCKSS', 'CLOCKSS', ['A national library', 'Trinity'], ['Other', 'A safe place']]", u"['LOCKSS', 'CLOCKSS', ['A national library', 'Trinity'], ['Other', 'A safe place']]", u"['LOCKSS', 'CLOCKSS', ['A national library', 'Trinity'], ['Other', 'A safe place']]", u"['LOCKSS', 'CLOCKSS', ['A national library', 'Trinity'], ['Other', 'A safe place']]"], do.bibjson.archiving_policy.policy

