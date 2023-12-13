from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, JSON, Table, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from geoalchemy2 import Geometry


Base = declarative_base()

class Feature(Base):
    __tablename__ = 'features'
    id = Column(Integer, primary_key=True)
    properties = Column(JSON)
    geometry_type = Column(String, nullable=False)
    geometry = Column(Geometry(geometry_type='GEOMETRY'), nullable=False)
    feature_set_id = Column(Integer, ForeignKey('feature_sets.id'))
    feature_set = relationship('FeatureSet', back_populates='features')

class FeatureSet(Base):
    __tablename__ = 'feature_sets'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    layer_id = Column(Integer, ForeignKey('layers.id'), nullable=False)
    layer = relationship('Layer', back_populates='feature_set')
    style_id = Column(Integer, ForeignKey('styles.id'), nullable=True)
    style = relationship('Style', back_populates='feature_sets')
    features = relationship('Feature', back_populates='feature_set')

class Layer(Base):
    __tablename__ = 'layers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    feature_set = relationship('FeatureSet', back_populates='layer')

class Colormap(Base):
    __tablename__ = 'colormaps'
    id = Column(Integer, primary_key=True)
    property = Column(String, nullable=False)
    min_value = Column(Float, nullable=False)
    max_value = Column(Float, nullable=False)
    min_color = Column(String, nullable=False)
    max_color = Column(String, nullable=False)
    styles = relationship('Style', back_populates='colormap')

class Style(Base):
    __tablename__ = 'styles'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    popup_properties = Column(JSON)
    border_color = Column(String)
    area_color = Column(String)
    icon_prefix = Column(String)
    icon_name = Column(String)
    icon_color = Column(String)
    line_weight = Column(Float)
    stroke = Column(Boolean) 
    opacity = Column(Float)
    line_cap = Column(String)
    line_join = Column(String)
    dash_array = Column(String)
    dash_offset = Column(String) # incompatible old browsers
    fill = Column(Boolean) 
    fill_opacity = Column(Float)
    fill_rule = Column(String)
    colormap_id = Column(Integer, ForeignKey('colormaps.id'), nullable=True)
    colormap = relationship('Colormap', back_populates='styles')
    feature_sets = relationship('FeatureSet', back_populates='style')

# create a connection
def connect_db(host="postgis", port=5432, user="postgres", password="rescuemate", echo=False):
    # build the connection string
    db_string = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    engine = create_engine(db_string, echo=echo)
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    return (engine, session)