import types

cdef class AbstractProperties:

	cdef dict __dict__

	cpdef _check_for_property(self, str name, object type=*)

	cdef _keep_only_cython_attribute(self, str name)

	cdef tuple[type, types.GetSetDescriptorType] _find_cython_descriptor(self, str name)

	cpdef _set_if_not_defined(self, str name, object value)

	cpdef _make_attribute_instance(self, str attr, object default)
