import daiquiri
from urllib.parse import quote, urlparse

from flask import (
    Blueprint, flash, render_template, redirect, request, url_for,
    session, Markup, jsonify, send_file
)

from flask_login import (
    current_user, login_required
)
import webapp.auth.user_data as user_data

import webapp.mimemail as mimemail

import webapp.config as Config
from webapp.home.metapype_client import (
    load_eml,
    is_hidden_button,
    handle_hidden_buttons
)
from webapp.buttons import *
from webapp.pages import *
from metapype.eml import names
from webapp.home.log_usage import (
    actions,
    log_usage,
)

from webapp.home.views import get_helps, set_current_page, open_document
from webapp.home.exceptions import (
    CollaboratingWithGroupAlready,
    InvitationBeingAcceptedByOwner,
    InvitationNotFound,
    UserIsNotTheOwner,
    UserNotFound
)

import webapp.views.collaborations.collaborations as collaborations
from webapp.views.collaborations.collaborations import (
    get_package_by_id,
    get_collaborations,
    get_invitations,
    get_collaboration_output,
    get_user_output,
    get_package_output,
    get_lock_output,
    release_acquired_lock
)
import webapp.views.collaborations.backups as collaboration_backups
from webapp.views.collaborations.forms import (
    CollaborateForm,
    EnableEDICurationForm,
    InviteCollaboratorForm,
    AcceptInvitationForm)

logger = daiquiri.getLogger('collab: ' + __name__)
collab_bp = Blueprint('collab', __name__, template_folder='templates')


@collab_bp.route('/collaborate', methods=['GET', 'POST'])
@collab_bp.route('/collaborate/<filename>', methods=['GET', 'POST'])
@collab_bp.route('/collaborate/<filename>/<dev>', methods=['GET', 'POST'])
@login_required
def collaborate(filename=None, dev=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DELETE, PAGE_DELETE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    form = CollaborateForm()

    # Process POST
    if request.method == 'POST':

        if not filename:
            filename = current_user.get_filename()

        if request.form.get(BTN_SUBMIT) == BTN_INVITE_COLLABORATOR:
            return redirect(url_for(PAGE_INVITE_COLLABORATOR, filename=filename, dev=dev))

        if request.form.get(BTN_SUBMIT) == BTN_ACCEPT_INVITATION:
            return redirect(url_for(PAGE_ACCEPT_INVITATION, filename=filename, dev=dev))

        if request.form.get(BTN_SUBMIT) == BTN_REFRESH:
            return redirect(url_for(PAGE_COLLABORATE, filename=filename, dev=dev))

        if request.form.get(BTN_SUBMIT) == BTN_CLEAN_UP_DATABASE:
            collaborations.cleanup_db()
            flash('The database has been cleaned up.', 'success')
            return redirect(url_for(PAGE_COLLABORATE, filename=filename, dev=dev))

    my_collaborations = get_collaborations(current_user.get_user_login())
    my_invitations = get_invitations(current_user.get_user_login())

    collaboration_list = get_collaboration_output()
    user_list = get_user_output()
    package_list = get_package_output()
    lock_list = get_lock_output()
    set_current_page('collaborate')
    if current_user.get_file_owner():
        owned_by_other = True
    else:
        owned_by_other = False
    invitation_disabled = owned_by_other or not current_user.get_filename()
    help = get_helps(['collaborate_general', 'collaborate_invite_accept'])

    return render_template('collaborate.html', collaborations=my_collaborations, invitations=my_invitations,
                           user=current_user.get_user_login(), invitation_disabled=invitation_disabled,
                           collaboration_list=collaboration_list, user_list=user_list, package_list=package_list,
                           lock_list=lock_list, help=help, dev=dev)


@collab_bp.route('/enable_edi_curation/<filename>', methods=['GET', 'POST'])
@login_required
def enable_edi_curation(filename=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DELETE, PAGE_DELETE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    form = EnableEDICurationForm()

    if request.method == 'POST':

        if request.form.get(BTN_SUBMIT):
            name = form.data['name']
            email_address = form.data['email_address']
            notes = form.data['notes']
            return redirect(url_for(PAGE_ENABLE_EDI_CURATION_2,
                                    filename=filename,
                                    name=name,
                                    email_address=email_address,
                                    notes=notes))

        if request.form.get(BTN_CANCEL):
            return redirect(url_for(PAGE_COLLABORATE, filename=current_user.get_filename()))

    return render_template('enable_edi_curation.html', filename=filename, form=form)


def enable_edi_curation_mail_body(filename=None, name=None, email_address=None, notes=None):
    msg = 'Dear EDI Data Curator:' + '\n\n' + \
        'This email was auto-generated by ezEML.\n\n\n' + \
        'An ezEML user has enabled EDI Curation.\n\n' + \
        '   User\'s name: ' + name + '\n\n' + \
        '   User\'s email: ' + email_address + '\n\n' + \
        '   Package name: ' + filename + '\n\n'
    if notes:
        msg += '   Sender\'s Notes: ' + notes
    return msg


@collab_bp.route('/enable_edi_curation_2/<filename>/<name>/<email_address>/<notes>', methods=['GET', 'POST'])
@login_required
def enable_edi_curation_2(filename=None, name=None, email_address=None, notes=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DELETE, PAGE_DELETE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    try:
        user_login = current_user.get_user_login()

        # Create a group collaboration with EDI Curators
        group_collaboration = collaborations.add_group_collaboration(user_login, 'EDI Curators', filename)

        # Activate group lock
        if group_collaboration:
            collaborations.add_group_lock(package_id=group_collaboration.package_id,
                                          locked_by=group_collaboration.user_group_id)

        # Back up the current package
        collaboration_backups.save_backup(group_collaboration.package_id)

        # Send an email to EDI Curators to let them know that a new package is available for curation
        msg = enable_edi_curation_mail_body(filename, name, email_address, notes)

        sent = mimemail.send_mail(subject='An ezEML user has enabled EDI curation',
                                  msg=msg,
                                  to=[Config.TO])
        if sent is True:
            log_usage(actions['ENABLE_EDI_CURATION'], name, email_address)
        flash('EDI curation has been enabled for this package.', 'success')

    except UserIsNotTheOwner:
        flash('Only the owner of the package can enable EDI curation for it.', 'error')
        # return redirect(url_for(PAGE_COLLABORATE, filename=filename))
    except CollaboratingWithGroupAlready:
        flash('EDI curation is already enabled for this package.', 'error')
        # return redirect(url_for(PAGE_COLLABORATE, filename=filename))
    except Exception as e:
        flash('An error occurred while enabling EDI curation for this package.', 'error')
        logger.error(e)

    return redirect(url_for(PAGE_COLLABORATE, filename=current_user.get_filename()))


@collab_bp.route('/accept_invitation', methods=['GET', 'POST'])
@collab_bp.route('/accept_invitation/<filename>', methods=['GET', 'POST'])
@collab_bp.route('/accept_invitation/<filename>/<invitation_code>', methods=['GET', 'POST'])
@login_required
def accept_invitation(filename=None, invitation_code=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DELETE, PAGE_DELETE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    form = AcceptInvitationForm()
    if request.method == 'POST' and form.validate_on_submit():
        if request.form.get(BTN_SUBMIT):
            invitation_code = form.invitation_code.data
            if invitation_code:
                user_login = current_user.get_user_login()
                try:
                    # Get the details on the invitation. It will be deleted if it is accepted, so we capture
                    #  the details here.
                    invitation = collaborations.get_invitation_by_code(invitation_code)
                    inviter_name = invitation.inviter_name
                    inviter_email = invitation.inviter_email
                    invitee_name = invitation.invitee_name
                    invitee_email = invitation.invitee_email
                    package_name = invitation.package.package_name

                    collaboration = collaborations.accept_invitation(user_login, invitation_code)
                    flash('You have successfully accepted the invitation.', 'success')

                    msg = compose_inform_inviter_of_acceptance_email(inviter_name, invitee_name,
                                                                     invitee_email, package_name)
                    sent = mimemail.send_mail(subject='Invitation to collaborate has been accepted',
                                              msg=msg,
                                              to=inviter_email,
                                              to_name=inviter_name)
                    if sent is True:
                        log_usage(actions['ACCEPT_INVITATION'], inviter_name, invitee_name)
                        flash(f'An email has been sent to {inviter_name} ({inviter_email}) to tell them you have accepted their invitation.',
                              'info')
                except InvitationNotFound:
                    flash('The invitation code was not found. Check that you entered it correctly. Otherwise, it '
                          'was already accepted, has expired, or has been cancelled.', 'error')
                except InvitationBeingAcceptedByOwner:
                    flash('You are the originator of this invitation. You cannot accept your own invitation.', 'error')
                except Exception as e:
                    flash(f'An error occurred while accepting the invitation. {e}', 'error')

        return redirect(url_for(PAGE_COLLABORATE, filename=filename))

    set_current_page('collaborate')
    help = get_helps(['invite_collaborator'])
    return render_template('accept_invitation.html',
                           title='Accept an Invitation',
                           form=form, help=help)


def compose_inform_inviter_of_acceptance_email(inviter_name, invitee_name, invitee_email, title):
    msg_raw = f'Dear {inviter_name}:\n\n' \
        f'{invitee_name} ({invitee_email}) has accepted your invitation to collaborate with you on editing the data ' \
        f'package "{title}" in ezEML.\n\n' \
        f'To manage the collaboration, go to the "Collaborate" page in ezEML.\n\n' \
        f'Thank you for using ezEML.'
    return msg_raw


def compose_invite_collaborator_email(name, sender_name, sender_email, title, invitation_code, ezeml_url):
    msg_html = Markup(f'Dear {name}:<p><br>'
        f'I am inviting you to collaborate with me on editing a data package in ezEML.<p><br>Data Package Title: "{title}"<p>' \
        f'To accept the invitation, please do the following:<p>' \
        f'- go to {ezeml_url} and log in using the login account you will use to edit the package<br>' \
        f'- in ezEML, click the "Collaborate" link<br>' \
        f'- on the "Collaborate" page, click the "Accept an Invitation" button<br>' \
        f'- enter this invitation code: <b>{invitation_code}</b><p>' \
        f'After you accept the invitation, you will be able to edit the data package with me in ezEML.<p>' \
        f'To learn more about ezEML, go to https://ezeml.edirepository.org.<p>' \
        f'Thanks!<p>{sender_name}<br>{sender_email}')
    msg_raw = f'Dear {name}:\n\n' \
        f'I am inviting you to collaborate with me on editing a data package in ezEML.\n\nData Package Title: "{title}"\n\n' \
        f'To accept the invitation, please do the following:\n' \
        f'- go to {ezeml_url} and log in using the login account you will use to edit the package\n' \
        f'- in ezEML, click the "Collaborate" link\n' \
        f'- on the "Collaborate" page, click the "Accept an Invitation" button\n' \
        f'- enter this invitation code: {invitation_code}\n\n' \
        f'After you accept the invitation, you will be able to edit the data package with me in ezEML.\n\n' \
        f'To learn more about ezEML, go to https://ezeml.edirepository.org.\n\n' \
        f'Thanks!\n\n{sender_name}\n{sender_email}'
    msg_quoted = f'mailto:{quote(msg_raw)}'
    return msg_quoted, msg_html, msg_raw


# @collab_bp.route('/invite_collaborator', methods=['GET', 'POST'])
@collab_bp.route('/invite_collaborator/<filename>', methods=['GET', 'POST'])
@login_required
def invite_collaborator(filename=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DELETE, PAGE_DELETE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    eml_node = load_eml(filename=filename)
    title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE])
    if not title_node or not title_node.content:
        flash('The data package must have a Title before a collaboration invitation can be sent.', 'error')
        return redirect(url_for(PAGE_TITLE, filename=filename))

    form = InviteCollaboratorForm()
    if request.method == 'POST' and form.validate_on_submit():
        # If the user has clicked Save in the EML Documents menu, for example, we want to ignore the
        #  programmatically generated Submit
        if request.form.get(BTN_SUBMIT) == BTN_SEND_INVITATION:

            user_name = form.data['user_name']
            user_email = form.data['user_email']

            collaborator_name = form.data['collaborator_name']
            email_address = form.data['email_address']
            title = title_node.content

            parsed_url = urlparse(request.base_url)
            ezeml_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"

            # Generate an Invitation record in the database
            invitation_code = collaborations.create_invitation(filename, user_name, user_email,
                                                               collaborator_name, email_address)

            try:
                mailto, mailto_html, mailto_raw = compose_invite_collaborator_email(collaborator_name,
                                                                                    user_name, user_email,
                                                                                    title, invitation_code,
                                                                                    ezeml_url)
            except Exception as e:
                collaborations.remove_invitation(invitation_code)
                raise

            subject = 'Invitation to collaborate on editing an ezEML data package'
            sent = mimemail.send_mail(subject=subject, msg=mailto_raw, to=email_address, to_name=collaborator_name)
            if sent is True:
                log_usage(actions['INVITE_COLLABORATOR'], collaborator_name, email_address)
                flash(f'An invitation has been sent to {collaborator_name} ({email_address}) to collaborate on editing the data package "{title}".')
                flash(f'When {collaborator_name} has accepted the invitation, you will be notified by email.', 'info')
                return redirect(url_for(PAGE_COLLABORATE, filename=filename))
            else:
                collaborations.remove_invitation(invitation_code)
                log_usage(actions['INVITE_COLLABORATOR'], 'failed')
                flash(sent, 'error')

    elif 'Cancel' in request.form:
        return redirect(url_for(PAGE_COLLABORATE, filename=filename))

    set_current_page('collaborate')
    help = get_helps(['invite_collaborator'])
    return render_template('invite_collaborator.html',
                           title=filename,
                           form=form, help=help)


@collab_bp.route('/remove_collaboration/<collab_id>', methods=['GET', 'POST'])
@collab_bp.route('/remove_collaboration/<collab_id>/<filename>', methods=['GET', 'POST'])
@login_required
def remove_collaboration(collab_id, filename=None):
    if not collab_id.startswith('G'):
        collaborations.remove_collaboration(collab_id)
    else:
        collab_id = int(collab_id[1:])
        collaborations.remove_group_collaboration(collab_id)
    return redirect(url_for(PAGE_COLLABORATE, filename=filename))


@collab_bp.route('/open_by_collaborator/<collaborator_id>/<package_id>', methods=['GET', 'POST'])
@login_required
def open_by_collaborator(collaborator_id, package_id):
    collaborator_id = int(collaborator_id)
    package_id = int(package_id)

    user_login = current_user.get_user_login()
    owner_login = collaborations.get_owner_login(package_id)
    package = get_package_by_id(package_id)
    if not owner_login or not package:
        flash('This collaboration is no longer active. Please contact the owner of the document.', 'error')
        return render_template('index.html')
    filename = package.package_name

    # Get a lock on the package, if available
    lock = collaborations.open_package(user_login, filename, owner_login=owner_login)
    # Open the document
    try:
        return open_document(filename, owner=collaborations.display_name(owner_login))
    except Exception as e:
        release_acquired_lock(lock)


@collab_bp.route('/apply_group_lock/<package_id>/<group_id>', methods=['GET', 'POST'])
@login_required
def apply_group_lock(package_id, group_id):
    collaborations.add_group_lock(int(package_id), group_id)
    current_document = user_data.get_active_document()
    return redirect(url_for(PAGE_COLLABORATE, filename=current_document))


@collab_bp.route('/release_group_lock/<package_id>', methods=['GET', 'POST'])
@login_required
def release_group_lock(package_id):
    # user_login = current_user.get_user_login()
    package_id = int(package_id)
    collaborations.release_group_lock(package_id)
    current_document = user_data.get_active_document()
    return redirect(url_for(PAGE_COLLABORATE, filename=current_document))


@collab_bp.route('/release_lock/<package_id>', methods=['GET', 'POST'])
@login_required
def release_lock(package_id):
    user_login = current_user.get_user_login()
    package_id = int(package_id)
    collaborations.release_lock(user_login, package_id)
    current_document = user_data.get_active_document()
    return redirect(url_for(PAGE_CLOSE, filename=current_document))


@collab_bp.route('/cancel_invitation/<invitation_id>', methods=['GET', 'POST'])
@collab_bp.route('/cancel_invitation/<invitation_id>/<filename>', methods=['GET', 'POST'])
@login_required
def cancel_invitation(invitation_id, filename=None):
    collaborations.cancel_invitation(invitation_id)
    if not filename:
        filename = user_data.get_active_document()
    return redirect(url_for(PAGE_COLLABORATE, filename=filename))
