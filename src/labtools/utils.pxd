
cdef class AbstractProperties:

	cdef dict __dict__
	cpdef _check_for_property(self, str name, object type=*)
	cpdef _set_if_not_defined(self, str name, object value)
	cpdef _make_attribute_instance(self, str attr, object default)
