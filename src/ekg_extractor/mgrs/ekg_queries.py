import configparser
import json
import os
from typing import List, Tuple

from neo4j import Driver, Result

from src.ekg_extractor.model.schema import Event, Entity, Activity
from src.ekg_extractor.model.semantics import EntityTree, EntityRelationship, EntityForest

config = configparser.ConfigParser()
if 'submodules' in os.listdir():
    curr_path = os.getcwd() + '/submodules/ekg_extractor'
else:
    curr_path = os.getcwd().split('src/ekg_extractor')[0]
config.read('{}/resources/config/config.ini'.format(curr_path))
config.sections()

SCHEMA_PATH = config['NEO4J SCHEMA']['schema.path'].format(curr_path, config['NEO4J SCHEMA']['schema.name'])
SCHEMA = json.load(open(SCHEMA_PATH))


class Ekg_Querier:
    def __init__(self, driver: Driver):
        self.driver = driver

    def get_events(self):
        with self.driver.session() as session:
            events_recs: Result = session.run("MATCH (e:{}) RETURN e".format(SCHEMA['event']))
            return [Event.parse_evt(e, SCHEMA['event_properties']) for e in events_recs.data()]

    def get_unique_events(self):
        all_events = self.get_events()
        unique_events = [e.activity for e in all_events]
        return set(unique_events)

    def get_events_by_timestamp(self, start_t: int = None, end_t: int = None):
        query = ""

        if start_t is not None and end_t is None:
            query = "MATCH (e:{}) WHERE e.{} > {} RETURN e " \
                    "ORDER BY e.{}".format(SCHEMA['event'], SCHEMA['event_properties']['timestamp'],
                                           str(start_t), SCHEMA['event_properties']['timestamp'])
        elif start_t is None and end_t is not None:
            query = "MATCH (e:{}) WHERE e.{} < {} RETURN e " \
                    "ORDER BY e.{}".format(SCHEMA['event'], SCHEMA['event_properties']['timestamp'],
                                           str(end_t), SCHEMA['event_properties']['timestamp'])
        elif start_t is not None and end_t is not None:
            query = "MATCH (e:{}) where e.{} > {} and e.{} < {} return e " \
                    "ORDER BY e.{}".format(SCHEMA['event'], SCHEMA['event_properties']['timestamp'],
                                           str(start_t), SCHEMA['event_properties']['timestamp'],
                                           str(end_t), SCHEMA['event_properties']['timestamp'])
        with self.driver.session() as session:
            events_recs: Result = session.run(query)
            return [Event.parse_evt(e, SCHEMA['event_properties']) for e in events_recs.data()]

    def get_events_by_date(self, start_t=None, end_t=None):
        query = ""

        if start_t is None and end_t is None:
            return self.get_events()

        if 'date' not in SCHEMA['event_properties']:
            return self.get_events_by_timestamp(start_t, end_t)
        elif start_t is not None and end_t is None:
            query = "MATCH (e:{}) WHERE e.{} > datetime({{epochmillis: apoc.date.parse(\"{}\", " \
                    "\"ms\", \"yyyy-MM-dd hh:mm:ss\")}}) RETURN e " \
                    "ORDER BY e.{}".format(SCHEMA['event'], SCHEMA['event_properties']['date'], str(start_t),
                                           SCHEMA['event_properties']['date'])
        elif start_t is None and end_t is not None:
            query = "MATCH (e:{}) WHERE e.{} < datetime({{epochmillis: apoc.date.parse(\"{}\", " \
                    "\"ms\", \"yyyy-MM-dd hh:mm:ss\")}}) RETURN e " \
                    "ORDER BY e.{}".format(SCHEMA['event'], SCHEMA['event_properties']['date'], str(end_t),
                                           SCHEMA['event_properties']['date'])
        elif start_t is not None and end_t is not None:
            query = "MATCH (e:{}) where e.{} > datetime({{epochmillis: apoc.date.parse(\"{}\", " \
                    "\"ms\", \"yyyy-MM-dd hh:mm:ss\")}}) and e.{} < datetime({{epochmillis: apoc.date.parse(\"{}\", " \
                    "\"ms\", \"yyyy-MM-dd hh:mm:ss\")}}) return e " \
                    "ORDER BY e.{}".format(SCHEMA['event'], SCHEMA['event_properties']['date'], str(start_t),
                                           SCHEMA['event_properties']['date'], str(end_t),
                                           SCHEMA['event_properties']['date'])
        with self.driver.session() as session:
            events_recs: Result = session.run(query)
            return [Event.parse_evt(e, SCHEMA['event_properties']) for e in events_recs.data()]

    def get_events_by_entity(self, en_id: str, pov: str = 'item'):
        arc = SCHEMA['event_to_item'] if pov.lower() == 'item' else SCHEMA['event_to_resource']

        # FIXME not great, preferable if a property is a primary key for any schema.
        if SCHEMA['entity_properties']['id'] != 'ID':
            query = "MATCH (e:{}) - [:{}] - (y:{}) WHERE toString(y.{}) = \"{}\" RETURN e " \
                    "ORDER BY e.{}".format(SCHEMA['event'], arc, SCHEMA['entity'],
                                           SCHEMA['entity_properties']['id'], en_id,
                                           SCHEMA['event_properties']['timestamp'])
        else:
            query = "MATCH (e:{}) - [:{}] - (y:{}) WHERE toString(ID(y)) = \"{}\" RETURN e " \
                    "ORDER BY e.{}".format(SCHEMA['event'], arc, SCHEMA['entity'],
                                           en_id, SCHEMA['event_properties']['timestamp'])
        with self.driver.session() as session:
            events_recs: Result = session.run(query)
            return [Event.parse_evt(e, SCHEMA['event_properties']) for e in events_recs.data()]

    def get_events_by_entity_tree(self, tree: EntityTree, pov: str = 'item'):
        events: List[Event] = []
        for node in tree.nodes:
            events.extend(self.get_events_by_entity(node.entity_id, pov))
        events.sort(key=lambda e: e.timestamp)
        return events

    def get_entities(self, limit: int = None, random: bool = False):
        query = "MATCH (e:{}) RETURN e".format(SCHEMA['entity'])

        if random:
            query = query + ', rand() as r ORDER BY r'

        if limit is not None:
            query = query + ' LIMIT {}'.format(limit)

        with self.driver.session() as session:
            entities = session.run(query)
            return [Entity.parse_ent(e, SCHEMA['entity_properties']) for e in entities.data()]

    def get_entity_by_id(self, entity_id: str):
        if SCHEMA['entity_properties']['id'] != 'ID':
            query = "MATCH (e:{}) WHERE toString(e.{}) = \"{}\" RETURN e".format(SCHEMA['entity'],
                                                                                 SCHEMA['entity_properties']['id'],
                                                                                 entity_id)
        else:
            query = "MATCH (e:{}) WHERE toString(ID(e)) = \"{}\" RETURN e,ID(e)".format(SCHEMA['entity'], entity_id)

        with self.driver.session() as session:
            results = session.run(query)
            # FIXME: not great, preferable if a property is a primary key for any schema.
            if SCHEMA['entity_properties']['id'] != 'ID':
                entities = [Entity.parse_ent(e, SCHEMA['entity_properties']) for e in results.data()]
            else:
                entities = [Entity.parse_ent(e, SCHEMA['entity_properties'], neo4_id=e['ID(e)']) for e in
                            results.data()]
            if len(entities) > 0:
                return entities[0]
            else:
                return None

    def get_entities_by_labels(self, labels: List[str] = None, limit: int = None, random: bool = False):
        if labels is None:
            return self.get_entities(limit, random)
        else:
            query_filter = "WHERE " + ' and '.join(["e:{}".format(l) for l in labels])

        query = "MATCH (e:{}) {} RETURN ID(e), e".format(SCHEMA['entity'], query_filter)

        if random:
            query = query + ', rand() as r ORDER BY r'

        if limit is not None:
            query = query + ' LIMIT {}'.format(limit)

        with self.driver.session() as session:
            entities = session.run(query)
            # FIXME: not great, preferable if a property is a primary key for any schema.
            if SCHEMA['entity_properties']['id'] != 'ID':
                return [Entity.parse_ent(e, SCHEMA['entity_properties']) for e in entities.data()]
            else:
                return [Entity.parse_ent(e, SCHEMA['entity_properties'], neo4_id=e['ID(e)']) for e in entities.data()]

    def get_items(self, labels_hierarchy=None, limit: int = None, random: bool = False):
        if labels_hierarchy is None:
            labels_hierarchy: List[List[str]] = self.get_entity_labels_hierarchy()
        if 'item' in SCHEMA:
            labels_seq = [seq for seq in labels_hierarchy if SCHEMA['item'] in seq][0]
            entities: List[Entity] = []
            for label in labels_seq:
                entities.extend(self.get_entities_by_labels(label.split('-'), limit, random))
            return entities
        else:
            return self.get_entities(limit, random)

    def get_resources(self, labels_hierarchy=None, limit: int = None, random: bool = False):
        if labels_hierarchy is None:
            labels_hierarchy: List[List[str]] = self.get_entity_labels_hierarchy()
        if 'resource' in SCHEMA:
            unpacked_labels_seq = [[label.split('-') for label in seq if '-' in label] for seq in labels_hierarchy]
            [labels_hierarchy.extend(labels) for labels in unpacked_labels_seq if len(labels) > 0]
            labels_seq = [seq for seq in labels_hierarchy if SCHEMA['resource'] in seq][0]
            entities: List[Entity] = []
            for label in labels_seq:
                entities.extend(self.get_entities_by_labels(label.split('-'), limit, random))
            return entities
        else:
            return self.get_entities(limit, random)

    def get_entity_labels_hierarchy(self):
        if 'entity_to_entity' not in SCHEMA:
            return [[l] for l in SCHEMA['entity_labels']]

        query = "MATCH (e1:{}) - [:{}] -> (e2:{}) RETURN labels(e1), labels(e2)".format(SCHEMA['entity'],
                                                                                        SCHEMA['entity_to_entity'],
                                                                                        SCHEMA['entity'])
        with self.driver.session() as session:
            results = session.run(query)

            rels: List[Tuple[str, str]] = []
            for res in results.data():
                rels.append(('-'.join([r for r in res['labels(e1)'] if r != SCHEMA['entity']]),
                             '-'.join([r for r in res['labels(e2)'] if r != SCHEMA['entity']])))

            return EntityTree.get_labels_hierarchy(set(rels))

    def get_entity_forest(self, labels_hierarchy: List[List[str]]):
        # WARNING: Builds tree for every entity in the KG, likely computational intensive.
        query_tplt = "MATCH (e1:{}) - [:{}] -> (e2:{}) WHERE {} RETURN e1, e2"
        trees: EntityForest = EntityForest([])
        for seq_i, seq in enumerate(labels_hierarchy):
            for i in range(len(seq) - 1, -1, -1):
                query_filter = 'e2:{}'.format(seq[i].split('-')[0]) + ''.join(
                    [' and e2:{}'.format(s) for s in seq[i].split('-')[1:]])
                query = query_tplt.format(SCHEMA['entity'], SCHEMA['entity_to_entity'], SCHEMA['entity'], query_filter)
                with self.driver.session() as session:
                    results = session.run(query)
                    entities: List[Tuple[Entity, Entity]] = [(Entity.parse_ent(r, SCHEMA['entity_properties'], 'e2'),
                                                              Entity.parse_ent(r, SCHEMA['entity_properties'], 'e1'))
                                                             for r in results.data()]
                    if len(entities) == 0:
                        continue

                    new_rels: List[EntityRelationship] = [EntityRelationship(tup[0], tup[1]) for tup in entities]
                    trees.add_trees([EntityTree([rel]) for rel in new_rels])

        return trees

    def get_entity_tree(self, entity_id: str, trees: EntityForest, reverse: bool = False):
        if 'entity_to_entity' not in SCHEMA:
            root_tree = EntityTree([])
            entity = self.get_entity_by_id(entity_id)
            if entity is None:
                return trees
            root_tree.nodes[entity] = []
            trees.add_trees([root_tree])
            return trees

        if reverse:
            query_tplt = "MATCH (e1:{}) <- [:{}] - (e2:{}) "
        else:
            query_tplt = "MATCH (e1:{}) - [:{}] -> (e2:{}) "

        query = query_tplt.format(SCHEMA['entity'], SCHEMA['entity_to_entity'], SCHEMA['entity'])
        query += "WHERE toString(e2.{}) = \"{}\" RETURN e1,e2".format(SCHEMA['entity_properties']['id'], entity_id)

        with self.driver.session() as session:
            results = session.run(query)
            entities: List[Tuple[Entity, Entity]] = [(Entity.parse_ent(r, SCHEMA['entity_properties'], 'e2'),
                                                      Entity.parse_ent(r, SCHEMA['entity_properties'], 'e1'))
                                                     for r in results.data()]
        if len(entities) == 0:
            root_tree = EntityTree([])
            entity = self.get_entity_by_id(entity_id)
            if entity is None:
                return trees
            root_tree.nodes[entity] = []
            trees.add_trees([root_tree])
            return trees

        new_rels: List[EntityRelationship] = [EntityRelationship(tup[0], tup[1]) for tup in entities]
        trees.add_trees([EntityTree([rel]) for rel in new_rels])
        children = [e[1].entity_id for e in entities]
        for child in children:
            self.get_entity_tree(child, trees, reverse)
        return trees

    def get_activities(self):
        with self.driver.session() as session:
            activities = session.run("MATCH (s:{}) RETURN s".format(SCHEMA['activity']))
            return [Activity.parse_act(s, SCHEMA['activity_properties']) for s in activities.data()]
