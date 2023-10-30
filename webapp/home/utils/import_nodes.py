"""
Helper functions for importing nodes from one EML document to another.

These pertain to operations like "Import Responsible Parties", "Import Geographic Coverage", etc.
Importing XML files and ezEML Data Packages are handled elsewhere.
"""

import webapp.auth.user_data as user_data
import webapp.home.utils.node_utils
from metapype.eml import names
from metapype.model.node import Node
from webapp.home.utils.load_and_save import load_eml, save_both_formats
from webapp.home.utils.node_utils import new_child_node, add_child


def reconcile_roles(node, target_class):
    """
    When importing a responsible party, the source node may or may not have a role and the target
    class may or may not require a role. If the target doesn't have role as an allowed child, remove
    the role, if present. If the target requires a role and the source doesn't have one, add a role
    child with empty content.
    """
    if target_class in ['Creators', 'Metadata Providers', 'Contacts']:
        role_node = node.find_child(names.ROLE)
        if role_node:
            webapp.home.utils.node_utils.remove_child(role_node)
    elif target_class in ['Associated Parties', 'Project Personnel']:
        role_node = node.find_child(names.ROLE)
        if not role_node:
            role_node = Node(names.ROLE)
            node.add_child(role_node)


def import_responsible_parties(target_package, node_ids_to_import, target_class):
    """
    Import responsible parties from the source package into the target package. The target class
    determines where the responsible parties will be imported. For example, if the target class is
    'Creators', the responsible parties will be imported into the target package as creators.

    node_ids_to_import is a list of node IDs of the responsible parties to import. The caller will
    have loaded the source package and the user will have selected which responsible parties to import.
    """
    # Load the target package's metadata.
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    # Find the dataset node, which is assumed to exist.
    dataset_node = target_eml_node.find_child(names.DATASET)
    if target_class in ['Creators', 'Metadata Providers', 'Associated Parties', 'Contacts', 'Publisher']:
        parent_node = dataset_node
    else:
        # Remaining case is 'Project Personnel'. This is treated differently because the personnel are children
        # of the project node, not the dataset node.
        project_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
        if not project_node:
            project_node = new_child_node(names.PROJECT, dataset_node)
        parent_node = project_node
    new_name = None
    if target_class == 'Creators':
        new_name = names.CREATOR
    elif target_class == 'Metadata Providers':
        new_name = names.METADATAPROVIDER
    elif target_class == 'Associated Parties':
        new_name = names.ASSOCIATEDPARTY
    elif target_class == 'Contacts':
        new_name = names.CONTACT
    elif target_class == 'Publisher':
        new_name = names.PUBLISHER
    elif target_class == 'Project Personnel':
        new_name = names.PERSONNEL
    # For each responsible party to import, create a new node and add it to the target package under the parent node
    #  identified above.
    for node_id in node_ids_to_import:
        node = Node.get_node_instance(node_id)
        new_node = node.copy()
        # The source node and target node may have different requirements regarding roles. Reconcile them.
        reconcile_roles(new_node, target_class)
        new_node.name = new_name
        add_child(parent_node, new_node)
    # Save the changes to the target package.
    save_both_formats(target_package, target_eml_node)


def import_keyword_nodes(target_package, node_ids_to_import):
    """
    Import keywords from the source package into the target package. The keywords will be imported into the
    target package's dataset node.

    node_ids_to_import is a list of node IDs of the keywords to import. The caller will have loaded the source
    package and the user will have selected which keywords to import.
    """
    # Load the target package's metadata.
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    # Find the dataset node, which is assumed to exist.
    dataset_node = target_eml_node.find_child(names.DATASET)
    # For each keyword to import, create a new keyword node and add it to the target package under the dataset node.
    for node_id in node_ids_to_import:
        keyword_set_node = Node(names.KEYWORDSET, parent=dataset_node)
        add_child(dataset_node, keyword_set_node)
        # Get the keyword node from the source package.
        source_node = Node.get_node_instance(node_id)
        # Copy the keyword node.
        new_keyword_node = source_node.copy()
        # See if the source node has a thesaurus node.
        keyword_thesaurus_node = source_node.parent.find_child(names.KEYWORDTHESAURUS)
        # If so, copy it.
        new_keyword_thesaurus_node = keyword_thesaurus_node.copy() if keyword_thesaurus_node else None
        # Add the keyword node and thesaurus node to the target package.
        add_child(keyword_set_node, new_keyword_node)
        if new_keyword_thesaurus_node:
            add_child(keyword_set_node, new_keyword_thesaurus_node)

    # Save the changes to the target package.
    save_both_formats(target_package, target_eml_node)


def import_coverage_nodes(target_package, node_ids_to_import):
    """
    Import geographic coverage or taxonomic coverage nodes from the source package into the target package.
    These nodes are children of the dataset's coverage node.

    The caller will have loaded the source package and the user will have selected which coverage nodes to import.
    """
    # Load the target package's metadata.
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    # Get the coverage node in the target package. If it doesn't exist, create it.
    parent_node = target_eml_node.find_single_node_by_path([names.DATASET, names.COVERAGE])
    if not parent_node:
        # No coverage node, so create one.
        dataset_node = target_eml_node.find_child(names.DATASET)
        coverage_node = Node(names.COVERAGE)
        add_child(dataset_node, coverage_node)
        parent_node = coverage_node
    # For the nodes to import, copy them and add them as children of the coverage node.
    for node_id in node_ids_to_import:
        node = Node.get_node_instance(node_id)
        new_node = node.copy()
        add_child(parent_node, new_node)
    # Save the changes to the target package.
    save_both_formats(target_package, target_eml_node)
    return target_eml_node


def import_funding_award_nodes(target_package, node_ids_to_import):
    """
    Import funding award nodes from the source package into the target package. These nodes are children of the
    dataset's project node.
    """
    # Load the target package's metadata.
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    # Find the dataset's project node. If it doesn't exist, create it.
    parent_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    if not parent_node:
        dataset_node = target_eml_node.find_child(names.DATASET)
        project_node = Node(names.PROJECT)
        add_child(dataset_node, project_node)
        parent_node = project_node
    # For each funding award node to import, copy it and add it as a child of the project node.
    for node_id in node_ids_to_import:
        node = Node.get_node_instance(node_id)
        new_node = node.copy()
        add_child(parent_node, new_node)
    # Save the changes to the target package.
    save_both_formats(target_package, target_eml_node)


def compose_funding_award_label(award_node:Node=None):
    """
    Compose a label for a funding award node. The label is a string that can be displayed to the user.
    """
    if not award_node:
        return ''
    title = ''
    title_node = award_node.find_child(names.TITLE)
    if title_node:
        title = title_node.content
    funder_name = ''
    funder_name_node = award_node.find_child(names.FUNDERNAME)
    if funder_name_node:
        funder_name = funder_name_node.content
    return f'{title}: {funder_name}'


def compose_project_label(project_node:Node=None):
    """
    Compose a label for a project node. The label is a string that can be displayed to the user.
    """
    if not project_node:
        return ''
    title = ''
    title_node = project_node.find_child(names.TITLE)
    if title_node:
        title = title_node.content
    return title


def import_project_node(target_package, node_id_to_import):
    """
    Import a project node from the source package into the target package. The project node is a child of the dataset
    node. The caller will have loaded the source package and provides the node_id of its project node.
    """
    if not node_id_to_import:
        return
    imported_node = Node.get_node_instance(node_id_to_import)
    if not imported_node:
        return
    # Load the target package's metadata.
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    # Find the target package's project node. If it exists, remove it, since we are about to replace it.
    project_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    if project_node:
        webapp.home.utils.node_utils.remove_child(project_node)
    # Copy the imported node and add it as a child of the dataset node.
    new_node = imported_node.copy()
    new_node.name = names.PROJECT
    # Remove any related projects. User will need to import any related projects separately.
    for child in new_node.find_all_children(names.RELATED_PROJECT):
        webapp.home.utils.node_utils.remove_child(child)
    # Add the new project node to the target package.
    dataset_node = target_eml_node.find_child(names.DATASET)
    add_child(dataset_node, new_node)
    # Save the changes to the target package.
    save_both_formats(target_package, target_eml_node)


def import_related_project_nodes(target_package, node_ids_to_import):
    """
    Import related project nodes from the source package into the target package. These nodes are children of the
    dataset's project node.
    """
    # Load the target package's metadata.
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    # Find the dataset's project node. If it doesn't exist, create it.
    parent_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    if not parent_node:
        dataset_node = target_eml_node.find_child(names.DATASET)
        project_node = Node(names.PROJECT)
        add_child(dataset_node, project_node)
        parent_node = project_node
    # For each related project node to import, copy it and add it as a child of the project node.
    for node_id in node_ids_to_import:
        node = Node.get_node_instance(node_id)
        new_node = node.copy()
        new_node.name = names.RELATED_PROJECT
        # If we're importing a project node as a related project, it may itself have relatedProject children.
        # If so, remove them.
        for child in new_node.find_all_children(names.RELATED_PROJECT):
            webapp.home.utils.node_utils.remove_child(child)
        # Add the new related project node to the target package as a child of the project node.
        add_child(parent_node, new_node)
    # Save the changes to the target package.
    save_both_formats(target_package, target_eml_node)


def compose_rp_label(rp_node:Node=None):
    """
    Compose a label for a responsible party node. The label is a string that can be displayed to the user.

    What we display for a responsible party depends on the type of responsible party, i.e. whether it is an individual,
    organization, or position. We also display the role, if any.
    """

    def compose_individual_name_label(rp_node: Node = None):
        label = ''
        if rp_node:
            salutation_nodes = rp_node.find_all_children(names.SALUTATION)
            if salutation_nodes:
                for salutation_node in salutation_nodes:
                    if salutation_node and salutation_node.content:
                        label = label + " " + salutation_node.content

            given_name_nodes = rp_node.find_all_children(names.GIVENNAME)
            if given_name_nodes:
                for given_name_node in given_name_nodes:
                    if given_name_node and given_name_node.content:
                        label = label + " " + given_name_node.content

            surname_node = rp_node.find_child(names.SURNAME)
            if surname_node and surname_node.content:
                label = label + " " + surname_node.content

        return label

    def compose_simple_label(rp_node: Node = None, child_node_name: str = ''):
        label = ''
        if rp_node and child_node_name:
            child_node = rp_node.find_child(child_node_name)
            if child_node and child_node.content:
                label = child_node.content
        return label

    label = ''
    if rp_node:
        individual_name_node = rp_node.find_child(names.INDIVIDUALNAME)
        individual_name_label = (
            compose_individual_name_label(individual_name_node))
        role_node = rp_node.find_child(names.ROLE)
        if role_node:
            role_label = role_node.content
        else:
            role_label = ''
        organization_name_label = (
            compose_simple_label(rp_node, names.ORGANIZATIONNAME))
        position_name_label = (
            compose_simple_label(rp_node, names.POSITIONNAME))

        if individual_name_label:
            label = individual_name_label
        if position_name_label:
            if label:
                label = label + ', '
            label = label + position_name_label
        if organization_name_label:
            if label:
                label = label + ', '
            label = label + organization_name_label
        if role_label:
            if label:
                label = label + ', '
            label = label + role_label
    return label
