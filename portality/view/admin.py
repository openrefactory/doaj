import json
import re

from flask import Blueprint, request, flash, abort, make_response
from flask import render_template, redirect, url_for
from flask.ext.login import current_user, login_required

from wtforms import Form, validators
from wtforms import Field, TextField, SelectField, TextAreaField, IntegerField, RadioField, BooleanField, FieldList
from wtforms.widgets import TextInput

from portality.core import app
import portality.models as models
import portality.util as util

# used by the journal edit form
import sys
try:
    if sys.version_info.major == 2 and sys.version_info.minor < 7:
        from portality.ordereddict import OrderedDict
except AttributeError:
    if sys.version_info[0] == 2 and sys.version_info[1] < 7:
        from portality.ordereddict import OrderedDict
    else:
        from collections import OrderedDict
else:
    from collections import OrderedDict

ISSN_REGEX = re.compile(r'^\d{4}-\d{3}(\d|X|x){1}$')

blueprint = Blueprint('admin', __name__)

# restrict everything in admin to logged in users with the "admin" role
@blueprint.before_request
def restrict():
    if current_user.is_anonymous() or not current_user.has_role("admin"):
        abort(401)    
    

# build an admin page where things can be done
@blueprint.route('/')
@login_required
def index():
    return render_template('admin/index.html')

@blueprint.route("/journals")
@login_required
def journals():
    return render_template('admin/journals.html',
               search_page=True,
               facetviews=['journals']
           )

@blueprint.route("/journal/<journal_id>", methods=["GET", "POST"])
@login_required
def journal_page(journal_id):
    if not current_user.has_role("edit_journal"):
        abort(401)
    j = models.Journal.pull(journal_id)
    if j is None:
        abort(404)

    with open('country-codes.json', 'rb') as f:
        countries = json.loads(f.read())
    countries = OrderedDict(sorted(countries.items(), key=lambda x: x[1]['name']))
    country_options = [('','')]
    for code, country_info in countries.items():
        country_options.append((code, country_info['name']))

    license_options = [
        ('', ''),
        ('CC by', 'Attribution'),
        ('CC by-nc', 'Attribution NonCommercial'),
        ('CC by-nc-nd', 'Attribution NonCommercial NoDerivatives'),
        ('CC by-nc-sa', 'Attribution NonCommercial ShareAlike'),
        ('CC by-nd', 'Attribution NoDerivatives'),
        ('CC by-sa', 'Attribution ShareAlike'),
    ]

    author_pays_options = [
        ('N', 'No charges'),
        ('CON', 'Conditional charges'),
        ('Y', 'Has charges'),
        ('NY', 'No information'),
    ]

    class TagListField(Field):
        widget = TextInput()
    
        def _value(self):
            if self.data:
                return u', '.join(self.data)
            else:
                return u''

        def get_list(self):
            return self.data
    
        def process_formdata(self, valuelist):
            if valuelist:
                self.data = [clean_x for clean_x in [x.strip() for x in valuelist[0].split(',')] if clean_x]
            else:
                self.data = []

    class IntegerAsStringField(Field):
        widget = TextInput()
    
        def _value(self):
            if self.data:
                return unicode(str(self.data))
            return u''

    class OptionalIf(validators.Optional):
        # a validator which makes a field optional if
        # another field is set and has a truthy value
    
        def __init__(self, other_field_name, *args, **kwargs):
            self.other_field_name = other_field_name
            super(OptionalIf, self).__init__(*args, **kwargs)
    
        def __call__(self, form, field):
            other_field = form._fields.get(self.other_field_name)
            if other_field is None:
                raise Exception('no field named "%s" in form' % self.other_field_name)
            if bool(other_field.data):
                super(OptionalIf, self).__call__(form, field)

    def validate_issn_list(id_type):

        def _validate_issn_list(form, field):
            data = field.get_list()
            if not data:
                return True

            error = '{id_type} #{which} is not valid. An {id_type} should be 7 or 8 digits long, separated by a dash, e.g. 1234-5678. If the {id_type} is 7 digits long, it must end with the letter X (e.g. 1234-567X).'
            for idx, issn in enumerate(data, start=1):
                if not ISSN_REGEX.match(issn):
                    raise validators.ValidationError(error.format(id_type=id_type, which=idx))
        return _validate_issn_list

    class JournalForm(Form):
        in_doaj = BooleanField('In DOAJ?')
        url = TextField('URL', [validators.Required()])
        title = TextField('Journal Title', [validators.Required()])
        pissn = TagListField('Journal ISSN', [OptionalIf('eissn'), validate_issn_list(id_type='ISSN')], description='(<strong>use commas</strong> to separate multiple ISSN-s)')
        eissn = TagListField('Journal EISSN', [OptionalIf('pissn'), validate_issn_list(id_type='EISSN')], description='(<strong>use commas</strong> to separate multiple EISSN-s)')
        publisher = TextField('Publisher', [validators.Required()])
        oa_start_year = IntegerAsStringField('Start year since online full text content is available', [validators.Required(), validators.NumberRange(min=1600)])
        country = SelectField('Country', [validators.Required()], choices=country_options)
        license = SelectField('Creative Commons (CC) License, if any', [validators.Optional()], choices=license_options)
        author_pays = RadioField('Author pays to publish', [validators.Required()], choices=author_pays_options)
        author_pays_url = TextField('Author pays - guide link', [validators.Optional()])
        keywords = TagListField('Keywords', [validators.Optional()], description='(<strong>use commas</strong> to separate multiple keywords)')
        languages = TagListField('Languages', [validators.Optional()], description='(What languages is the <strong>full text</strong> published in? <strong>Use commas</strong> to separate multiple languages.)')
    
    current_info = {
        'in_doaj': j.is_in_doaj(),
        'url': j.bibjson().get_single_url(urltype='homepage'),
        'title': j.bibjson().title,
        'pissn': j.bibjson().get_identifiers(j.bibjson().P_ISSN),
        'eissn': j.bibjson().get_identifiers(j.bibjson().E_ISSN),
        'publisher': j.bibjson().publisher,
        'oa_start_year': j.bibjson().oa_start.get('year', ''),
        'country': j.bibjson().country,
        'license': j.bibjson().get_license(),
        'author_pays': j.bibjson().author_pays,
        'author_pays_url': j.bibjson().author_pays_url,
        'keywords': j.bibjson().keywords,
        'languages': j.bibjson().language,
    }

    form = JournalForm(request.form, **current_info)
    if request.method == 'POST' and form.validate():
        nj = j
        nj.bibjson().active = form.in_doaj.data
        nj.set_in_doaj(form.in_doaj.data)
        nj.bibjson().update_url(form.url.data, 'homepage')
        nj.bibjson().title = form.title.data
        nj.bibjson().update_identifiers(nj.bibjson().P_ISSN, form.pissn.get_list())
        nj.bibjson().update_identifiers(nj.bibjson().E_ISSN, form.eissn.get_list())
        nj.bibjson().publisher = form.publisher.data
        nj.bibjson().set_oa_start(year=form.oa_start_year.data)
        nj.bibjson().country = form.country.data
        nj.bibjson().set_license(license_title=form.license.data, license_type=form.license.data)
        nj.bibjson().author_pays = form.author_pays.data
        nj.bibjson().author_pays_url = form.author_pays_url.data
        nj.bibjson().set_keywords(form.keywords.data)
        nj.bibjson().set_language(form.languages.data)
        print nj.data
        json.dumps(nj.data)
        #nj.save()

    return render_template("admin/journal.html", form=form, journal=j)

@blueprint.route("/suggestions")
@login_required
def suggestions():
    return render_template('admin/suggestions.html',
               search_page=True,
               facetviews=['suggestions']
           )

@blueprint.route("/suggestion/<suggestion_id>", methods=["GET", "POST"])
@login_required
def suggestion_page(suggestion_id):
    if not current_user.has_role("edit_suggestion"):
        abort(401)
    s = models.Suggestion.pull(suggestion_id)
    if s is None:
        abort(404)
        
    if request.method == "GET":
        return render_template("admin/suggestion.html", suggestion=s)

    elif request.method == "POST":
        req = json.loads(request.data)
        new_status = req.get("status")
        s.set_application_status(new_status)
        s.save()
        return "", 204


