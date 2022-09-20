from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)
from flask_login import (
    login_required
)

from webapp.home.forms import (
    form_md5, is_dirty_form
)

from webapp.home.views import process_up_button, process_down_button

from webapp.home.metapype_client import (
    load_eml, save_both_formats,
    add_child, remove_child,
    UP_ARROW, DOWN_ARROW,
    handle_hidden_buttons, check_val_for_hidden_buttons
)

from webapp.home.texttype_node_processing import (
    display_texttype_node,
    model_has_complex_texttypes,
    invalid_xml_error_message,
    is_valid_xml_fragment
)

from webapp.views.method_steps.forms import (
    MethodStepForm, MethodStepSelectForm
)
from webapp.home.views import set_current_page, get_help

from webapp.buttons import *
from webapp.pages import *

from metapype.eml import names
from metapype.model.node import Node
from webapp.home.metapype_client import (
    create_method_step,
    list_method_steps
)


md_bp = Blueprint('md', __name__, template_folder='templates')
data_sources_marker_begin = '==================== Data Sources ========================='
data_sources_marker_end = '==========================================================='


@md_bp.route('/method_step_select/<filename>', methods=['GET', 'POST'])
@login_required
def method_step_select(filename=None):
    form = MethodStepSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        node_id = ''
        new_page = ''
        url = ''
        this_page = PAGE_METHOD_STEP_SELECT
        edit_page = PAGE_METHOD_STEP
        back_page = PAGE_PUBLICATION_INFO
        next_page = PAGE_PROJECT

        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                if val == BTN_BACK:
                    new_page = back_page
                elif val in [BTN_NEXT, BTN_SAVE_AND_CONTINUE]:
                    new_page = next_page
                elif val == BTN_EDIT:
                    new_page = edit_page
                    node_id = key
                elif val == BTN_REMOVE:
                    new_page = this_page
                    node_id = key
                    eml_node = load_eml(filename=filename)
                    remove_child(node_id=node_id)
                    save_both_formats(filename=filename, eml_node=eml_node)
                elif val == UP_ARROW:
                    new_page = this_page
                    node_id = key
                    process_up_button(filename, node_id)
                elif val == DOWN_ARROW:
                    new_page = this_page
                    node_id = key
                    process_down_button(filename, node_id)
                elif val[0:3] == 'Add':
                    new_page = edit_page
                    node_id = '1'
                elif val == '[  ]':
                    new_page = this_page
                    node_id = key
                else:
                    new_page = check_val_for_hidden_buttons(val, new_page, this_page)

        if form.validate_on_submit():
            if new_page in [edit_page, this_page]:
                url = url_for(new_page,
                              filename=filename,
                              node_id=node_id)
            else:
                url = url_for(new_page,
                              filename=filename)
            return redirect(url)

    # Process GET
    method_step_list = []
    title = 'Method Steps'
    eml_node = load_eml(filename=filename)

    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            method_step_list = list_method_steps(dataset_node)

    set_current_page('method_step')
    help = [get_help('methods')]
    return render_template('method_step_select.html', title=title,
                           filename=filename,
                           method_step_list=method_step_list,
                           form=form, help=help)


# node_id is the id of the methodStep node being edited. If the value is
# '1', it means we are adding a new methodStep node, otherwise we are
# editing an existing one.
#
@md_bp.route('/method_step/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def method_step(filename=None, node_id=None):
    eml_node = load_eml(filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)

    if dataset_node:
        methods_node = dataset_node.find_child(names.METHODS)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

    if not methods_node:
        methods_node = Node(names.METHODS, parent=dataset_node)
        add_child(dataset_node, methods_node)

    form = MethodStepForm(filename=filename, node_id=node_id)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_METHOD_STEP_SELECT, filename=filename)
            return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        new_page = PAGE_METHOD_STEP_SELECT  # Save or Back sends us back to the list of method steps

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                new_page = check_val_for_hidden_buttons(val, new_page, PAGE_METHOD_STEP)

        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'

        if submit_type == 'Save Changes':
            description = form.description.data
            valid, msg = is_valid_xml_fragment(description, names.MAINTENANCE)
            if not valid:
                flash(invalid_xml_error_message(msg, False, names.DESCRIPTION), 'error')
                return render_get_method_step_page(eml_node, form, filename)

            instrumentation = form.instrumentation.data
            data_sources = form.data_sources.data
            method_step_node = Node.get_node_instance(node_id)
            if not method_step_node:
                method_step_node = Node(names.METHODSTEP, parent=methods_node)
                add_child(methods_node, method_step_node)
            create_method_step(method_step_node, description, instrumentation, data_sources,
                               data_sources_marker_begin, data_sources_marker_end)

            save_both_formats(filename=filename, eml_node=eml_node)

        url = url_for(new_page, filename=filename)
        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        method_step_nodes = methods_node.find_all_children(names.METHODSTEP)
        if method_step_nodes:
            for ms_node in method_step_nodes:
                if node_id == ms_node.id:
                    populate_method_step_form(form, ms_node)
                    break
    return render_get_method_step_page(eml_node, form, filename)


def render_get_method_step_page(eml_node, form, filename):
    set_current_page('method_step')
    help = [get_help('method_step_description'), get_help('method_step_instrumentation'), get_help('method_step_data_sources')]
    return render_template('method_step.html', title='Method Step',
                           model_has_complex_texttypes=model_has_complex_texttypes(eml_node),
                           form=form, filename=filename, help=help)


def populate_method_step_form(form: MethodStepForm, ms_node: Node):
    description = ''
    instrumentation = ''
    data_sources = ''

    if ms_node:
        description_node = ms_node.find_child(names.DESCRIPTION)
        if description_node:
            description = display_texttype_node(description_node)
            if data_sources_marker_begin in description and data_sources_marker_end in description:
                begin = description.find(data_sources_marker_begin)
                end = description.find(data_sources_marker_end)
                data_sources = description[begin+len(data_sources_marker_begin)+1:end-1]
                description = description[0:begin-1]

        instrumentation_node = ms_node.find_child(names.INSTRUMENTATION)
        if instrumentation_node:
            instrumentation = instrumentation_node.content

        form.description.data = description
        form.instrumentation.data = instrumentation
        form.data_sources.data = data_sources
    form.md5.data = form_md5(form)

