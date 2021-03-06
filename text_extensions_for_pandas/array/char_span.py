#
#  Copyright (c) 2020 IBM Corp.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

#
# char_span.py
#
# Part of text_extensions_for_pandas
#
# Pandas extensions to support columns of spans with character offsets.
#
import textwrap
from typing import *

import numpy as np
import pandas as pd
from memoized_property import memoized_property

# Internal imports
import text_extensions_for_pandas.util as util


class CharSpan:
    """
    Python object representation of a single span with character offsets; that
    is, a single row of a `CharSpanArray`.

    An offset of `CharSpan.NULL_OFFSET_VALUE` (currently -1) indicates
    "not a span" in the sense that NaN is "not a number".
    """

    # Begin/end value that indicates "not a span" in the sense that NaN is
    # "not a number".
    NULL_OFFSET_VALUE = -1  # Type: int

    def __init__(self, text: str, begin: int, end: int):
        """
        Args:
            text: target document text on which the span is defined
            begin: Begin offset (inclusive) within `text`
            end: End offset (exclusive, one past the last char) within `text`
        """
        if CharSpan.NULL_OFFSET_VALUE == begin:
            if CharSpan.NULL_OFFSET_VALUE != end:
                raise ValueError("Begin offset with special 'null' value {} "
                                 "must be paired with an end offset of {}",
                                 CharSpan.NULL_OFFSET_VALUE,
                                 CharSpan.NULL_OFFSET_VALUE)
        elif begin < 0:
            raise ValueError("begin must be >= 0")
        elif end < 0:
            raise ValueError("end must be >= 0")
        elif end > len(text):
            raise ValueError(f"end must be less than length of target string "
                             f"({end} > {len(text)}")
        self._text = text
        self._begin = begin
        self._end = end

    def __repr__(self) -> str:
        return "[{}, {}): '{}'".format(self.begin, self.end,
                                       textwrap.shorten(self.covered_text, 80))

    def __eq__(self, other):
        if isinstance(other, CharSpan):
            return (self.begin == other.begin
                    and self.end == other.end
                    and self.target_text == other.target_text)
        elif isinstance(other, CharSpanArray):
            return other == self
        else:
            # Different type ==> not equal
            return False

    def __hash__(self):
        result = hash((self.target_text, self.begin, self.end))
        return result

    def __lt__(self, other):
        """
        span1 < span2 if span1.end <= span2.begin
        """
        # TODO: Should we compare target strings?
        if isinstance(other, (CharSpan, CharSpanArray)):
            return self.end <= other.begin
        else:
            raise ValueError("Less-than relationship not defined for {} and {} "
                             "of types {} and {}"
                             "".format(self, other, type(self), type(other)))

    def __gt__(self, other):
        return other < self

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return other <= self

    @property
    def begin(self):
        return self._begin

    @property
    def end(self):
        return self._end

    @property
    def target_text(self):
        return self._text

    @memoized_property
    def covered_text(self):
        """
        Returns the substring of `self.target_text` that this `CharSpan`
        represents.
        """
        if CharSpan.NULL_OFFSET_VALUE == self._begin:
            return None
        else:
            return self.target_text[self.begin:self.end]

    def overlaps(self, other: "CharSpan"):
        """
        :param other: Another CharSpan or TokenSpan
        :return: True if the two spans overlap. Also True if a zero-length
            span is contained within the other.
        """
        if self.begin == other.begin and self.end == other.end:
            # Ensure that pairs of identical zero-length spans overlap.
            return True
        elif other.begin >= self.end:
            return False  # other completely to the right of self
        elif other.end <= self.begin:
            return False  # other completely to the left of self
        else:  # other.begin < self.end and other.end >= self.begin
            return True

    def contains(self, other: "CharSpan"):
        """
        :param other: Another CharSpan or TokenSpan
        :return: True if `other` is entirely within the bounds of this span. Also
            True if a zero-length span is contained within the other.
        """
        return other.begin >= self.begin and other.end <= self.end

    def context(self, num_chars: int = 40) -> str:
        """
        Show the location of this span in the context of the target string.

        :param num_chars: How many characters on either side to display
        :return: A string in the form:
         ```<text before>[<text inside>]<text after>```
         describing the text within and around the span.
        """
        before_text = self.target_text[self.begin - num_chars:self.begin]
        after_text = self.target_text[self.end:self.end + num_chars]
        if self.begin > num_chars:
            before_text = "..." + before_text
        if self.end + num_chars < len(self.target_text):
            after_text = after_text + "..."
        return f"{before_text}[{self.covered_text}]{after_text}"


@pd.api.extensions.register_extension_dtype
class CharSpanType(pd.api.extensions.ExtensionDtype):
    """
    Panda datatype for a span that represents a range of characters within a
    target string.
    """

    @property
    def type(self):
        # The type for a single row of a column of type CharSpan
        return CharSpan

    @property
    def name(self) -> str:
        """A string representation of the dtype."""
        return "CharSpanType"

    @classmethod
    def construct_from_string(cls, string: str):
        """
        See docstring in `ExtensionDType` class in `pandas/core/dtypes/base.py`
        for information about this method.
        """
        # Upstream code uses exceptions as part of its normal control flow and
        # will pass this method bogus class names.
        if string == cls.__name__:
            return cls()
        else:
            raise TypeError(
                f"Cannot construct a '{cls.__name__}' from '{string}'")

    @classmethod
    def construct_array_type(cls):
        """
        See docstring in `ExtensionDType` class in `pandas/core/dtypes/base.py`
        for information about this method.
        """
        return CharSpanArray

    def __from_arrow__(self, extension_array):
        """
        Convert the given extension array of type ArrowCharSpanType to a
        CharSpanArray.
        """
        from text_extensions_for_pandas.array.arrow_conversion import arrow_to_char_span
        return arrow_to_char_span(extension_array)


class CharSpanArray(pd.api.extensions.ExtensionArray):
    """
    A Pandas `ExtensionArray` that represents a column of character-based spans
    over a single target text.

    Spans are represented as `[begin, end)` intervals, where `begin` and `end`
    are character offsets into the target text.
    """

    def __init__(self, text: str,
                 begins: Union[pd.Series, np.ndarray, Sequence[int]],
                 ends: Union[pd.Series, np.ndarray, Sequence[int]]):
        """
        :param text: Target text from which the spans of this array are drawn
        :param begins: Begin offsets of spans (closed)
        :param ends: End offsets (open)
        """
        if not isinstance(begins, (pd.Series, np.ndarray, list)):
            raise TypeError(f"begins is of unsupported type {type(begins)}. "
                            f"Supported types are Series, ndarray and List[int].")
        if not isinstance(ends, (pd.Series, np.ndarray, list)):
            raise TypeError(f"ends is of unsupported type {type(ends)}. "
                            f"Supported types are Series, ndarray and List[int].")
        begins = np.array(begins) if not isinstance(begins, np.ndarray) else begins
        ends = np.array(ends) if not isinstance(ends, np.ndarray) else ends

        if not np.issubdtype(begins.dtype, np.integer):
            raise TypeError(f"Begins array is of dtype {begins.dtype}, "
                            f"which is not an integer type.")
        if not np.issubdtype(ends.dtype, np.integer):
            raise TypeError(f"Ends array is of dtype {begins.dtype}, "
                            f"which is not an integer type.")

        self._text = text  # Type: str
        self._begins = begins  # Type: np.ndarray
        self._ends = ends  # Type: np.ndarray

        # Monotonically increasing version number for tracking changes and
        # invalidating caches
        self._version = 0  # Type: int

        # Cached list of other CharSpanArrays that are exactly the same as this
        # one. Each element is the result of calling id()
        self._equivalent_arrays = []  # Type: List[int]

        # Version numbers of elements in self._equivalent_arrays, to ensure that
        # a change hasn't made the arrays no longer equal
        self._equiv_array_versions = []  # Type: List[int]

        self._shared_init()

    def _shared_init(self):
        """
        Initialization steps shared between CharSpanArray and TokenSpanArray
        """
        # Cached hash value of this array
        self._hash = None

        # Flag that tells whether to display details of offsets in Jupyter notebooks
        self._repr_html_show_offsets = True

    ##########################################
    # Overrides of superclass methods go here.

    @property
    def dtype(self) -> pd.api.extensions.ExtensionDtype:
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        return CharSpanType()

    def __len__(self) -> int:
        return len(self._begins)

    def __getitem__(self, item) -> Union[CharSpan, "CharSpanArray"]:
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        if isinstance(item, int):
            return CharSpan(self._text, int(self._begins[item]),
                            int(self._ends[item]))
        else:
            # item not an int --> assume it's a numpy-compatible index
            return CharSpanArray(self._text,
                                 self._begins[item],
                                 self._ends[item])

    def __setitem__(self, key: Union[int, np.ndarray], value: Any) -> None:
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        if isinstance(key, np.ndarray):
            raise NotImplementedError("Setting multiple rows at once not "
                                      "implemented")
        if not isinstance(key, int):
            raise NotImplementedError(f"Don't understand key type "
                                      f"'{type(key)}'")
        if value is None:
            self._begins[key] = CharSpan.NULL_OFFSET_VALUE
            self._ends[key] = CharSpan.NULL_OFFSET_VALUE
        elif not isinstance(value, CharSpan):
            raise ValueError(
                f"Attempted to set element of CharSpanArray with"
                f"an object of type {type(value)}")
        else:
            self._begins[key] = value.begin
            self._ends[key] = value.end
        # We just changed the contents of this array, so invalidate any cached
        # results computed from those contents.
        self.increment_version()

    def __eq__(self, other):
        """
        Pandas/Numpy-style array/series comparison function.

        :param other: Second operand of a Pandas "==" comparison with the series
        that wraps this TokenSpanArray.

        :return: Returns a boolean mask indicating which rows match `other`.
        """
        if isinstance(other, CharSpan):
            mask = np.full(len(self), True, dtype=np.bool)
            mask[self.target_text != other.target_text] = False
            mask[self.begin != other.begin] = False
            mask[self.end != other.end] = False
            return mask
        elif isinstance(other, CharSpanArray):
            if len(self) != len(other):
                raise ValueError("Can't compare arrays of differing lengths "
                                 "{} and {}".format(len(self), len(other)))
            if self.target_text != other.target_text:
                return np.zeros(self.begin.shape, dtype=np.bool)
            return np.logical_and(
                self.begin == self.begin,
                self.end == self.end
            )
        else:
            # TODO: Return False here once we're sure that this
            #  function is catching all the comparisons that really matter.
            raise ValueError("Don't know how to compare objects of type "
                             "'{}' and '{}'".format(type(self), type(other)))

    def __ne__(self, other):
        return ~(self == other)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self._text, self._begins.tobytes(),
                               self._ends.tobytes()))
        return self._hash

    def equals(self, other: "CharSpanArray"):
        """
        :param other: A second `CharSpanArray`
        :return: True if both arrays have the same target text (can be a
        different string object with the same contents) and the same spans
        in the same order.
        """
        if not isinstance(other, CharSpanArray):
            raise TypeError(f"equals() not defined for arguments of type "
                            f"{type(other)}")
        if self is other:
            return True

        # Check for cached result
        if id(other) in self._equivalent_arrays:
            cache_ix = self._equivalent_arrays.index(id(other))
        else:
            cache_ix = -1

        if (cache_ix >= 0
                and other.version == self._equiv_array_versions[cache_ix]):
            # Cached "equal" result
            return True
        elif (self.target_text != other.target_text
              or not np.array_equal(self.begin, other.begin)
              or not np.array_equal(self.end, other.end)):
            # "Not equal" result from slow path
            if cache_ix >= 0:
                del self._equivalent_arrays[cache_ix]
                del self._equiv_array_versions[cache_ix]
            return False
        else:
            # If we get here, self and other are equal, and we had to expend
            # quite a bit of effort to figure that out.
            # Cache the result so we don't have to do that again.
            if cache_ix >= 0:
                self._equiv_array_versions[cache_ix] = other.version
            else:
                self._equivalent_arrays.append(id(other))
                self._equiv_array_versions.append(other.version)
            return True

    @classmethod
    def _concat_same_type(
        cls, to_concat: Sequence[pd.api.extensions.ExtensionArray]
    ) -> pd.api.extensions.ExtensionArray:
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        text = {a.target_text for a in to_concat}
        if len(text) != 1:
            raise ValueError("CharSpans must all be over the same target text")
        text = text.pop()

        begins = np.concatenate([a.begin for a in to_concat])
        ends = np.concatenate([a.end for a in to_concat])
        return CharSpanArray(text, begins, ends)

    @classmethod
    def _from_sequence(cls, scalars, dtype=None, copy=False):
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        text = None
        begins = np.full(len(scalars), CharSpan.NULL_OFFSET_VALUE, np.int)
        ends = np.full(len(scalars), CharSpan.NULL_OFFSET_VALUE, np.int)
        i = 0
        for s in scalars:
            if not isinstance(s, CharSpan):
                raise ValueError(f"Can only convert a sequence of CharSpan "
                                 f"objects to a CharSpanArray. Found an "
                                 f"object of type {type(s)}")
            if text is None:
                text = s.target_text
            if s.target_text != text:
                raise ValueError(
                    f"Mixing different target texts is not currently "
                    f"supported. Received two different strings:\n"
                    f"{text}\nand\n{s.target_text}")
            begins[i] = s.begin
            ends[i] = s.end
            i += 1
        return CharSpanArray(text, begins, ends)

    def isna(self) -> np.array:
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        return np.equal(self._begins, CharSpan.NULL_OFFSET_VALUE)

    def copy(self) -> "CharSpanArray":
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        ret = CharSpanArray(
            self.target_text,
            self.begin.copy(),
            self.end.copy()
        )
        # TODO: Copy cached properties too
        return ret

    def take(
        self, indices: Sequence[int], allow_fill: bool = False,
        fill_value: Any = None
    ) -> "CharSpanArray":
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        if allow_fill:
            # From API docs: "[If allow_fill == True, then] negative values in
            # `indices` indicate missing values. These values are set to
            # `fill_value`.  Any other negative values raise a ``ValueError``."
            if fill_value is None or np.math.isnan(fill_value):
                # Replace with a "nan span"
                fill_value = CharSpan(
                    self.target_text,
                    CharSpan.NULL_OFFSET_VALUE,
                    CharSpan.NULL_OFFSET_VALUE)
            elif not isinstance(fill_value, CharSpan):
                raise ValueError("Fill value must be Null, nan, or a CharSpan "
                                 "(was {})".format(fill_value))
        else:
            # Dummy fill value to keep code below happy
            fill_value = CharSpan(self.target_text, CharSpan.NULL_OFFSET_VALUE,
                                  CharSpan.NULL_OFFSET_VALUE)

        # Pandas' internal implementation of take() does most of the heavy
        # lifting.
        begins = pd.api.extensions.take(
            self.begin, indices, allow_fill=allow_fill,
            fill_value=fill_value.begin
        )
        ends = pd.api.extensions.take(
            self.end, indices, allow_fill=allow_fill,
            fill_value=fill_value.end
        )
        return CharSpanArray(self.target_text, begins, ends)

    def __lt__(self, other):
        """
        Pandas-style array/series comparison function.

        :param other: Second operand of a Pandas "<" comparison with the series
        that wraps this TokenSpanArray.

        :return: Returns a boolean mask indicating which rows are less than
         `other`. span1 < span2 if span1.end <= span2.begin.
        """
        if isinstance(other, (CharSpanArray, CharSpan)):
            return self.end <= other.begin
        else:
            raise ValueError("'<' relationship not defined for {} and {} "
                             "of types {} and {}"
                             "".format(self, other, type(self), type(other)))

    def __gt__(self, other):
        return other < self

    def __le__(self, other):
        # TODO: Figure out what the semantics of this operation should be.
        raise NotImplementedError()

    def __ge__(self, other):
        # TODO: Figure out what the semantics of this operation should be.
        raise NotImplementedError()

    def _reduce(self, name, skipna=True, **kwargs):
        """
        See docstring in `ExtensionArray` class in `pandas/core/arrays/base.py`
        for information about this method.
        """
        if name == "sum":
            # Sum ==> combine, i.e. return the smallest span that contains all
            #         spans in the series
            return CharSpan(self.target_text, np.min(self.begin),
                            np.max(self.end))
        else:
            raise TypeError(f"'{name}' aggregation not supported on a series "
                            f"backed by a CharSpanArray")

    ####################################################
    # Methods that don't override the superclass go here

    @classmethod
    def make_array(cls, o) -> "CharSpanArray":
        """
        Make a `CharSpanArray` object out of any of several types of input.

        :param o: a CharSpanArray object represented as a `pd.Series`, a list
        of `TokenSpan` objects, or maybe just an actual `CharSpanArray`
        (or `TokenSpanArray`) object.

        :return: CharSpanArray version of `o`, which may be a pointer to `o` or
        one of its fields.
        """
        if isinstance(o, CharSpanArray):
            return o
        elif isinstance(o, pd.Series):
            return cls.make_array(o.values)
        elif isinstance(o, Iterable):
            return cls._from_sequence(o)

    @property
    def target_text(self) -> str:
        """
        Returns the common "document" text that the spans in this array
        reference.
        """
        return self._text

    @property
    def begin(self) -> np.ndarray:
        return self._begins

    @property
    def end(self) -> np.ndarray:
        return self._ends

    @property
    def version(self) -> int:
        """
        :return: Monotonically increasing version number that changes every time
        this array is modified. **NOTE:** This number might not change if a
        caller obtains a pointer to an internal array and modifies it.
        Callers who perform such modifications should call `increment_version()`
        """
        return self._version

    def increment_version(self):
        """
        Manually increase the version counter of this array to indicate that
        the array's contents have changed. Also invalidates any internal cached
        data derived from the array's state.
        """
        # Invalidate cached computation
        self._equivalent_arrays = []
        self._equiv_array_versions = []
        self._hash = None

        # Increment the counter
        self._version += 1

    def as_tuples(self) -> np.ndarray:
        """
        Returns (begin, end) pairs as an array of tuples
        """
        return np.concatenate(
            (self.begin.reshape((-1, 1)), self.end.reshape((-1, 1))),
            axis=1)

    @property
    def covered_text(self) -> np.ndarray:
        """
        :return: an array of the substrings of `target_text` corresponding to
        the spans in this array.
        """
        # TODO: Vectorized version of this
        text = self.target_text
        # Need dtype=np.object so we can return nulls
        result = np.zeros(len(self), dtype=np.object)
        for i in range(len(self)):
            if self._begins[i] == CharSpan.NULL_OFFSET_VALUE:
                # Null value at this index
                result[i] = None
            else:
                result[i] = text[self._begins[i]:self._ends[i]]
        return result

    @memoized_property
    def normalized_covered_text(self) -> np.ndarray:
        """
        :return: A normalized version of the covered text of the spans in this
          array. Currently "normalized" means "lowercase".
        """
        # Currently we can't use np.char.lower directly because
        # self.covered_text needs to be an object array, not a numpy string
        # array, to allow for null values.
        return np.vectorize(np.char.lower)(self.covered_text)

    def as_frame(self) -> pd.DataFrame:
        """
        Returns a dataframe representation of this column based on Python
        atomic types.
        """
        return pd.DataFrame({
            "begin": self.begin,
            "end": self.end,
            "covered_text": self.covered_text
        })

    def overlaps(self, other: Union["CharSpanArray", CharSpan]):
        """
        :param other: Either a single span or an array of spans of the same
            length as this one
        :return: Numpy array containing a boolean mask of all entries that
            overlap the corresponding element of `other`
        """
        if not isinstance(other, (CharSpan, CharSpanArray)):
            raise TypeError(f"overlaps not defined for input type "
                            f"{type(other)}")

        # Replicate the logic in CharSpan.overlaps() with boolean masks
        exact_equal_mask = np.logical_and(self.begin == other.begin,
                                          self.end == other.end)
        begin_ge_end_mask = other.begin >= self.end
        end_le_begin_mask = other.end <= self.begin

        # (self.begin == other.begin and self.end == other.end)
        # or not (other.begin >= self.end or other.end <= self.begin)
        return np.logical_or(exact_equal_mask,
                             np.logical_not(
                                 np.logical_or(begin_ge_end_mask,
                                               end_le_begin_mask)))

    def contains(self, other: Union["CharSpanArray", CharSpan]):
        """
        :param other: Either a single span or an array of spans of the same
            length as this one
        :return: Numpy array containing a boolean mask of all entries that
            contain the corresponding element of `other`
        """
        if not isinstance(other, (CharSpan, CharSpanArray)):
            raise TypeError(f"contains not defined for input type "
                            f"{type(other)}")

        # Replicate the logic in CharSpan.contains() with boolean masks
        begin_ge_begin_mask = other.begin >= self.begin
        end_le_end_mask = other.end <= self.end
        return np.logical_and(begin_ge_begin_mask, end_le_end_mask)

    def _repr_html_(self) -> str:
        """
        HTML pretty-printing of a series of spans for Jupyter notebooks.
        """
        return util.pretty_print_html(self, self._repr_html_show_offsets)

    @property
    def repr_html_show_offsets(self):
        """
        @returns: Whether the HTML/Jupyter notebook representation of this array will
         contain a table of span offsets in addition to the marked-up target text.
        """
        return self._repr_html_show_offsets

    @repr_html_show_offsets.setter
    def repr_html_show_offsets(self, show_offsets: bool):
        self._repr_html_show_offsets = show_offsets

    def __arrow_array__(self, type=None):
        """
        Conversion of this Array to a pyarrow.ExtensionArray.
        :param type: Optional type passed to arrow for conversion, not used
        :return: pyarrow.ExtensionArray of type ArrowCharSpanType
        """
        from text_extensions_for_pandas.array.arrow_conversion import char_span_to_arrow
        return char_span_to_arrow(self)
