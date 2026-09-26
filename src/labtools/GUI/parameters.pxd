
from labtools._tools.abstract_properties cimport AbstractProperties

cdef class GUIParametrable(AbstractProperties):
    cdef public str title

    cpdef _set_if_not_defined(self, str name, object value)

    cpdef get_parameters(self, object frame, object view)

    cpdef create_group(self, object frame)

    cpdef create_widget(self, object frame, object view)

    cpdef destroy(self)