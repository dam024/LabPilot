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

from labpilot.data_management.database_manager import Base


class Versionable:

    """This class provides features to its subclasses to allow them to handle versioning of an object/process/etc.

    Attributes:
        version (str): Version of the object
    """


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

    pass


class SampleTemplate(Base):

    """Defines a type of sample that can be measured. A Sample Template containes a list of definition for the different properties of the sample."""

    pass


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

    pass


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

    pass


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

    pass


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

    pass


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

    pass
