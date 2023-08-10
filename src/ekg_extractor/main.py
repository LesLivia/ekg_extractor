from neo4j.exceptions import AuthError

import src.ekg_extractor.mgrs.db_connector as conn
from src.ekg_extractor.logger.logger import Logger
from src.ekg_extractor.mgrs.ekg_queries import Ekg_Querier
from src.ekg_extractor.model.semantics import EntityForest

LOGGER = Logger('main')

LOGGER.info('Starting...')

try:
    driver = conn.get_driver()
    querier = Ekg_Querier(driver)

    entity_label_hierarchy = querier.get_entity_labels_hierarchy()

    entity = querier.get_entities_by_labels(entity_label_hierarchy[0][0].split('-'), 1, True)[0]
    print(entity.entity_id)

    entity_tree = querier.get_entity_tree(entity.entity_id, EntityForest([]), reverse=True)

    events = querier.get_events_by_entity_tree(entity_tree.trees[0])
    for e in events:
        print(e.activity, e.timestamp)

    conn.close_connection(driver)
    LOGGER.info('EKG querying done.')
except AuthError:
    LOGGER.error('Connection to DB could not be established.')
