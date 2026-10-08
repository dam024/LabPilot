"""Summary

Attributes:
    Base (TYPE): Description
    charlie (TYPE): Description
    engine (TYPE): Description
    result (TYPE): Description
    Session (TYPE): Description
    session (TYPE): Description
    tissue (TYPE): Description
"""
import datetime
from enum import Enum
from pathlib import Path

import sqlalchemy
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.mutable import MutableDict

from labtools.data_management.database_manager import Base


class Versionable:

    """This class provides features to its subclasses to allow them to handle versioning of an object/process/etc.

    Attributes:
        version (str): Version of the object
    """

    version = Column(String, nullable=False, comment="Version of the ", default="1.0.0")
    """Version of the object"""


# class Setup(Base, Versionable):
#    __tablename__ = "setup"
#    measurements = relationship('Measurement',back_populates="setup")


class Experiment(Base, Versionable):

    """Informations relative to an experiment. An experiment is defined as a procedure to take a measurement.

    Attributes:
        description (str): Description of the experiment
        id (int): Primary key
        name (str): Name of the experiment
    """

    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True)
    """Primary key"""
    name = Column(String, nullable=False, unique=True)
    """Name of the experiment"""
    description = Column(String)
    """Description of the experiment"""


class SampleTemplate(Base):

    """Defines a type of sample that can be measured. A Sample Template containes a list of definition for the different properties of the sample."""

    __tablename__ = "sample_templates"
    id = Column(Integer, primary_key=True)
    """Primary key"""
    name = Column(String, nullable=False, unique=True)
    """Name of the template"""
    description = Column(String)
    """Description of the sample type"""

    samples = relationship("Sample", back_populates="template")
    """List of samples using the current template"""
    properties = relationship("SamplePropertyTemplate", back_populates="template")
    """Properties associated with the sample"""


class PropertyType(Enum):

    """Defines types that can be used for values of a property"""

    STRING = "String"
    INT = "Int"
    FLOAT = "Float"
    DATE = "Date"
    DATETIME = "DateTime"
    BOOLEAN = "Boolean"


class SamplePropertyTemplate(Base):

    """Definition of a property that can be used for a sample.

    This class defines the property itself, as well as how it can be used and defined.

    Note:
        - Handling of types: All values are saved as string in the database. Once the property is retrieved, its type will be parsed to the appropriate value.
    """

    __tablename__ = "sample_property_templates"
    id = Column(Integer, primary_key=True)
    """Primary key"""
    template_id = Column(Integer, ForeignKey(SampleTemplate.id))
    """ForeignKey for the sample template associated to this property"""

    template = relationship("SampleTemplate", back_populates="properties")
    """Sample Template to which the current property belongs to"""

    name = Column(String, nullable=False, unique=True)
    """Name of the property"""
    type = Column(
        sqlalchemy.Enum(
            PropertyType, values_clallable=lambda t: [str(item.value) for item in t]
        )
    )
    """Type of data of the property"""
    default_value = Column(String)
    """Default value of the property"""
    required = Column(Boolean, nullable=False, default=True)
    """Indicates if the property is required for the sample"""
    unique = Column(Boolean, nullable=False, default=True)
    """Indicates if the property is unique or can be defined multiple times"""


class Sample(Base):

    """Summary

    Attributes:
        description (TYPE): Description
        id (TYPE): Description
        measurements (TYPE): Description
        name (TYPE): Description
        properties (TYPE): Description
        template (TYPE): Description
        template_id (TYPE): Description
    """

    __tablename__ = "samples"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String)
    template_id = Column(Integer, ForeignKey(SampleTemplate.id))

    template = relationship("SampleTemplate", back_populates="samples")
    properties = relationship("SampleProperty", back_populates="sample")
    measurements = relationship("Measurement", back_populates="sample")


class SampleProperty(Base):

    """Summary

    Attributes:
        id (TYPE): Description
        property_template (TYPE): Description
        property_template_id (TYPE): Description
        sample (TYPE): Description
        sample_id (TYPE): Description
        value (TYPE): Description
    """

    __tablename__ = "sample_properties"
    id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey(Sample.id))
    sample = relationship("Sample", back_populates="properties")
    property_template_id = Column(Integer, ForeignKey(SamplePropertyTemplate.id))
    property_template = relationship("SamplePropertyTemplate")
    value = Column(String)


class Measurement(Base):

    """Summary

    Attributes:
        description (TYPE): Description
        experiment (TYPE): Description
        experiment_id (TYPE): Description
        id (TYPE): Description
        name (TYPE): Description
        recordings (TYPE): Description
        sample (TYPE): Description
        sample_id (TYPE): Description
    """

    __tablename__ = "measurements"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    experiment_id = Column(Integer, ForeignKey(Experiment.id))
    experiment = relationship("Experiment")
    # setup_id = Column(Integer, ForeignKey(Setup.__tablename__+'.id'))
    # setup = relationship('Setup',back_populates="measurements")
    sample_id = Column(Integer, ForeignKey(Sample.id))
    sample = relationship("Sample", back_populates="measurements")
    recordings = relationship("Recording", back_populates="measurement")


class Recording(Base):

    """Summary

    Attributes:
        description (TYPE): Description
        end (TYPE): Description
        id (TYPE): Description
        measurement (TYPE): Description
        measurement_id (TYPE): Description
        readers (TYPE): Description
        start (TYPE): Description
    """

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str]
    readers: Mapped[str]
    start: Mapped[datetime.datetime] = mapped_column(nullable=False)
    end: Mapped[datetime.datetime] = mapped_column(nullable=False)
    measurement_id: Mapped[int] = mapped_column(ForeignKey(Measurement.id))
    measurement: Mapped[Measurement] = relationship(
        "Measurement", back_populates="recordings"
    )
    parameters: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)


if False:
    # new_person = Person(name="Charlie", age=70)
    # session.add(new_person)
    # session.flush()  # Temporary write the data, so that we can rollback the changes in case
    #
    # new_thing = Thing(description="Camera", value=500, owner=new_person.id)
    # session.add(new_thing)
    charlie = session.query(Person).filter(Person.name == "Charlie").all()[0]

    tissue = Thing(description="Tissue", value=1.5, owner=charlie.id)
    session.add(tissue)
    session.commit()

    # session.commit()

    result = session.query(Thing).all()

    print(result)

    result = session.query(Thing).filter(Thing.value < 50).delete()
    session.commit()

    result = session.query(Thing).all()

    print(result)

if False:
    from sqlalchemy import (
        Float,
        ForeignKey,
        create_engine,
        MetaData,
        Table,
        Column,
        Integer,
        String,
        func,
    )

    engine = create_engine("sqlite:///mydatabase.db", echo=True)

    # Create meta data
    meta = MetaData()

    people = Table(
        "people",
        meta,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
        Column("age", Integer),
    )
    things = Table(
        "things",
        meta,
        Column("id", Integer, primary_key=True),
        Column("description", String, nullable=False),
        Column("value", Float),
        Column("owner", Integer, ForeignKey("people.id")),  # 1 to many relationship
    )

    # Create the table
    meta.create_all(engine)

    conn = engine.connect()

    # Insert data
    if False:
        insert_people = people.insert().values(
            [
                {"name": "Mike", "age": 30},
                {"name": "Bob", "age": 35},
                {"name": "Anna", "age": 38},
                {"name": "John", "age": 50},
                {"name": "Clara", "age": 42},
            ]
        )

        insert_things = things.insert().values(
            [
                {"owner": 2, "description": "Laptop", "value": 800.5},
                {"owner": 2, "description": "Mouse", "value": 50.5},
                {"owner": 2, "description": "Keyboard", "value": 100.5},
                {"owner": 3, "description": "Book", "value": 30},
                {"owner": 4, "description": "Bottle", "value": 10.5},
                {"owner": 5, "description": "Speakers", "value": 80.5},
            ]
        )

        conn.execute(insert_people)
        # conn.commit()
        conn.execute(insert_things)
        conn.commit()

    # select
    join_statement = people.join(things, people.c.id == things.c.owner)
    select_statement = (
        people.select()
        .with_only_columns(people.c.name, things.c.description)
        .select_from(join_statement)
    )
    result = conn.execute(select_statement)

    for row in result.fetchall():
        print(row)

    print()
    group_by_statement = (
        things.select()
        .with_only_columns(things.c.owner, func.sum(things.c.value))
        .group_by(things.c.owner)
    )
    result = conn.execute(group_by_statement)
    for row in result.fetchall():
        print(row)
