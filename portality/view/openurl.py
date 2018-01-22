import re
from flask import Blueprint, request, redirect, url_for, render_template, abort
from portality.models import OpenURLRequest
from portality.lib import analytics
from portality.core import app
from urllib import unquote

blueprint = Blueprint('openurl', __name__)


@blueprint.route("/openurl", methods=["GET", "POST"])
def openurl():
    # check that we've been given some arguments at all
    if len(request.values) == 0:
        abort(404)

    # Validate the query syntax version and build an object representing it
    parser_response = parse_query(query=unquote(request.query_string), req=request)

    # theoretically this can return None, so catch it
    if parser_response is None:
        abort(404)

    # If it's not parsed to an OpenURLRequest, it's a redirect URL to try again.
    if type(parser_response) != OpenURLRequest:
        return redirect(parser_response, 301)

    # Get the OpenURLRequest object to issue a query and supply a url for the result
    result_url = parser_response.get_result_url()
    if result_url:
        return redirect(result_url)
    else:
        abort(404)


@analytics.sends_ga_event('OpenURL', 'Retrieve', record_value_of_which_arg='query')
def parse_query(query, req):
    """
    Create the model which holds the query
    :param query: The query string from the request URL (separated for the sake of analytics)
    :param req: an incoming OpenURL request
    :return: an object representing the query, or a redirect to the reissued query, or None if failed.
    """
    # Check if this is new or old syntax, translate if necessary
    if "url_ver=Z39.88-2004" not in query:
        app.logger.info("Legacy OpenURL 0.1 request: " + unquote(req.url))
        return old_to_new(req)

    app.logger.info("OpenURL 1.0 request: " + unquote(req.url))

    # Wee function to strip of the referent namespace prefix from parameters
    rem_ns = lambda x: re.sub('rft.', '', x)

    # Pack the list of parameters into a dictionary, while un-escaping the string.
    dict_params = {rem_ns(key): value for (key, value) in req.values.iteritems()}

    # Create an object to represent this OpenURL request.
    try:
        query_object = OpenURLRequest(**dict_params)
    except:
        query_object = None
        app.logger.info("Failed to create OpenURLRequest object")

    return query_object


def old_to_new(req):
    """
    Translate the OpenURL 0.1 syntax to 1.0, to provide a redirect.
    :param req: An incoming OpenURL request
    :return: An OpenURL 1.0 query string
    """

    # The meta parameters in the preamble.
    params = {'url_ver': 'Z39.88-2004', 'url_ctx_fmt': 'info:ofi/fmt:kev:mtx:ctx', 'rft_val_fmt': 'info:ofi/fmt:kev:mtx:journal'}

    # In OpenURL 0.1, jtitle is just title. This function substitutes them.
    sub_title = lambda x: re.sub('^title', 'jtitle', x)

    # Add referent tags to each parameter, and change title tag using above function
    rewritten_params = {"rft." + sub_title(key): value for (key, value) in req.values.iteritems()}

    # Add the rewritten parameters to the meta params
    params.update(rewritten_params)

    return url_for('.openurl', **params)


@blueprint.route("/openurl/help")
def help():
    return render_template("openurl/help.html")


@blueprint.errorhandler(404)
def bad_request(e):
    return render_template("openurl/404.html"), 404
