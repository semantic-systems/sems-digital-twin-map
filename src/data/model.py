from sqlalchemy import Column, Integer, String, ForeignKey, Float, JSON, Boolean, DateTime, Table
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

Base = declarative_base()

# Association Table for many-to-many relationship between FeatureSets and Scenarios
feature_set_scenario_association = Table(
    'feature_set_scenario_association',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('feature_set_id', Integer, ForeignKey('feature_sets.id'), nullable=False),
    Column('scenario_id', Integer, ForeignKey('scenarios.id'), nullable=False)
)

class Feature(Base):
    """
    Table name: features
    - `properties` [JSON] Properties of the feature. You can control which properties are displayed in the popup by setting the `popup_properties` attribute of the style.
    - `geometry_type` [String] Type of the geometry
    - `geometry` [Geometry] Geometry of the feature. Possible values: ```{Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon}```
    - `feature_set_id` [Integer] ID of the FeatureSet the feature belongs to
    - `feature_set` [FeatureSet] FeatureSet the feature belongs to
    """
    __tablename__ = 'features'
    id = Column(Integer, primary_key=True)
    properties = Column(JSON)
    timestamp = Column(DateTime, nullable=True)
    geometry_type = Column(String, nullable=False)
    geometry = Column(Geometry(geometry_type='GEOMETRY'), nullable=False)
    feature_set_id = Column(Integer, ForeignKey('feature_sets.id'), nullable=False)
    feature_set = relationship('FeatureSet', back_populates='features')

class FeatureSet(Base):
    """
    Table name: feature_sets
    - `name` [String] Name of the feature set
    - `features` [Feature Array] List of features that belong to the feature set
    - `layer_id` [Integer] ID of the layer the feature set belongs to
    - `layer` [Layer] Layer the feature set belongs to
    - `style_id` [Integer] ID of the style to be used for the feature set
    - `style` [Style] Style to be used for the feature set
    - `collection_id` [Integer] (Optional) ID of the Collection the feature set belongs to
    - `collection` [Collection] (Optional) The Collection the feature set belongs to
    """
    __tablename__ = 'feature_sets'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    features = relationship('Feature', back_populates='feature_set')

    layer_id = Column(Integer, ForeignKey('layers.id'), nullable=False)
    layer = relationship('Layer', back_populates='feature_sets')

    style_id = Column(Integer, ForeignKey('styles.id'), nullable=False)
    style = relationship('Style', back_populates='feature_sets')

    features = relationship('Feature', back_populates='feature_set')

    collection_id = Column(Integer, ForeignKey('collections.id'), nullable=True)    # nullable, because the feature set might not be associated with a collection
    collection = relationship('Collection', back_populates='feature_sets')

    scenarios = relationship('Scenario', secondary=feature_set_scenario_association, back_populates='feature_sets') # many-to-many relationship to scenarios

class Layer(Base):
    """
    Table name: layers
    - `name` [String] Name of the layer. Gets displayed in the UI
    - `feature_sets` [FeatureSet Array] List of FeatureSets that belong to the layer
    """
    __tablename__ = 'layers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    feature_sets = relationship('FeatureSet', back_populates='layer')

class Dataset(Base):
    """
    Table name: datasets
    - `name` [String] Name of the dataset. Gets displayed in the UI
    - `description` [String] Description of the dataset. Gets displayed in the UI
    - `url` [String] URL to the dataset
    - `collection_identifiers` [String Array] List of identifiers of the collection. Only collections with these identifiers will be requested and displayed.
    - `collections` [Collection Array] List of collections that belong to the dataset
    """
    __tablename__ = 'datasets'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    url = Column(String, nullable=False)
    collection_identifiers = Column(ARRAY(String), nullable=False)
    collections = relationship('Collection', back_populates='dataset')

class Collection(Base):
    """
    Table name: collections
    - `identifier` [String] Identifier of the collection, for example "hauptdeichlinie"
    - `name` [String] Name of the collection. Gets displayed in the UI
    - `url_items` [String] URL to the items of the collection. You can download the items as GeoJSON from this URL
    - `url_collection` [String] URL to the collection
    - `entries` [Integer] Number of items in the collection. Request this number of features from the api using ?limit=ENTRIES
    - `dataset_id` [Integer] ID of the dataset the collection belongs to
    - `dataset` [Dataset] Dataset the collection belongs to
    - `feature_sets` [FeatureSet Array] List of FeatureSets that use the collection
    """
    __tablename__ = 'collections'
    id = Column(Integer, primary_key=True)
    identifier = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url_items = Column(String, nullable=False)
    url_collection = Column(String, nullable=False)
    entries = Column(Integer, nullable=False)

    dataset_id = Column(Integer, ForeignKey('datasets.id'), nullable=False)
    dataset = relationship('Dataset', back_populates='collections')

    feature_sets = relationship('FeatureSet', back_populates='collection')


class Scenario(Base):
    """
    A logical grouping of FeatureSets for a single use case
    Table name: scenarios
    - `name` [String] Name of the scenario
    - `description` [String] Description of the scenario
    - `feature_sets` [FeatureSet Array] List of FeatureSets that belong to the scenario
    """
    __tablename__ = 'scenarios'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    
    # Many-to-Many Relationship to FeatureSet
    feature_sets = relationship('FeatureSet', secondary=feature_set_scenario_association, back_populates='scenarios')

class Colormap(Base):
    """
    Table name: colormaps
    - `property` [String] Feature Property to be mapped
    - `min_value` [Float] Minimum value of the property
    - `max_value` [Float] Maximum value of the property
    - `min_color` [String] Hex color for the minimum value
    - `max_color` [String] Hex color for the maximum value
    - `styles` [Style Array] List of styles that use the colormap
    """
    __tablename__ = 'colormaps'
    id = Column(Integer, primary_key=True)
    property = Column(String, nullable=False)
    min_value = Column(Float, nullable=False)
    max_value = Column(Float, nullable=False)
    min_color = Column(String, nullable=False)
    max_color = Column(String, nullable=False)
    styles = relationship('Style', back_populates='colormap')

class Style(Base):
    """
    Table name: styles
    For most styling attributes, check out the [Leaflet Path documentation](https://leafletjs.com/reference.html#path).
    - `name` [String] Name of the style
    - `popup_properties` [JSON] List of properties to be displayed in the popup, the value is the name of the property, the key is the label
    - `marker_icon` [String] The icon to be used for the marker. Check out [fontawesome.com](https://fontawesome.com/search?o=r&m=free&s=solid) for a list of usable icons.
    - `marker_color` [String] Color of the marker. Possible values: ```{red, darkred, lightred, orange, beige, green, darkgreen,
    lightgreen, blue, darkblue, lightblue, purple, darkpurple, pink, cadetblue, white, gray, lightgray, black}```
    - `colormap_id` [Integer] ID of the colormap to be used for the style
    - `colormap` [Colormap] Colormap to be used for the style. Overrides 
    - `feature_sets` [FeatureSet Array] List of feature sets that use the style
    """
    __tablename__ = 'styles'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    popup_properties = Column(JSON)
    border_color = Column(String)
    area_color = Column(String)
    marker_icon = Column(String)
    marker_color = Column(String)
    line_weight = Column(Float)
    stroke = Column(Boolean) 
    opacity = Column(Float)
    line_cap = Column(String)
    line_join = Column(String)
    dash_array = Column(String)
    dash_offset = Column(String)    # incompatible with old browsers
    fill = Column(Boolean) 
    fill_opacity = Column(Float)
    fill_rule = Column(String)
    colormap_id = Column(Integer, ForeignKey('colormaps.id'), nullable=True)
    colormap = relationship('Colormap', back_populates='styles')
    feature_sets = relationship('FeatureSet', back_populates='style')