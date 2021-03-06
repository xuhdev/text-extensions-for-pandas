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

import os
import tempfile
import textwrap
import unittest

import numpy as np
import numpy.testing as npt
import pandas as pd

from text_extensions_for_pandas.array.tensor import TensorArray


class TestTensor(unittest.TestCase):
    def setUp(self):
        # Ensure that diffs are consistent
        pd.set_option("display.max_columns", 250)

    def tearDown(self):
        pd.reset_option("display.max_columns")

    def test_create(self):
        x = np.ones([5, 2, 3])
        s = TensorArray(x)
        self.assertEqual(len(s), 5)

        x = [np.ones([2, 3])] * 5
        s = TensorArray(x)
        self.assertEqual(len(s), 5)

        x = np.empty((0, 2))
        s = TensorArray(x)
        self.assertEqual(len(s), 0)
        s = TensorArray([])
        self.assertEqual(len(s), 0)

        x = [np.ones([2, 3]), np.ones([3, 2])]
        with self.assertRaises(ValueError):
            TensorArray(x)

        with self.assertRaises(TypeError):
            TensorArray(2112)

    def test_operations(self):
        x = np.ones([5, 3])

        # equal
        s1 = TensorArray(x)
        s2 = TensorArray(x)
        self.assertTrue(np.all(s1 == s2))

        # less, greater
        s2 = TensorArray(x * 2)
        self.assertTrue(np.all(s1 < s2))
        self.assertFalse(np.any(s1 > s2))

        # add TensorArrays
        s1 = TensorArray(x * 2)
        s2 = TensorArray(x * 3)
        result = s1 + s2
        self.assertTrue(isinstance(result, TensorArray))
        npt.assert_equal(result.to_numpy().shape, [5, 3])
        self.assertTrue(np.all(result == 5))

        # multiply TensorArrays
        s1 = TensorArray(x * 2)
        s2 = TensorArray(x * 3)
        result = s1 * s2
        npt.assert_equal(result.to_numpy().shape, [5, 3])
        self.assertTrue(np.all(result == 6))

        # multiply scalar
        s1 = TensorArray(x * 2)
        result = s1 * 4
        npt.assert_equal(result.to_numpy().shape, [5, 3])
        self.assertTrue(np.all(result == 8))

    def test_setitem(self):
        x = np.array([[1, 2], [3, 4], [5, 6]])
        a = TensorArray(x)
        a[1] = np.array([42, 42])
        npt.assert_equal(a[1], [42, 42])

    def test_repr(self):
        x = np.array([[1, 2], [3, 4], [5, 6]])
        expected = textwrap.dedent(
            """\
        array([[1, 2],
               [3, 4],
               [5, 6]])"""
        )
        s = TensorArray(x)
        result = s.__repr__()
        self.assertEqual(expected, result)

        result = repr(pd.Series(s))
        expected = textwrap.dedent(
            """\
            0   [1 2]
            1   [3 4]
            2   [5 6]
            dtype: TensorType"""
        )
        self.assertEqual(expected, result)

        # The following currently doesn't work, due to
        # https://github.com/pandas-dev/pandas/issues/33770
        # TODO: Re-enable when a version of Pandas with a fix is released.
        # y = np.array([[True, False], [False, True], [False, False]])
        # s = TensorArray(y)
        # result = s.__repr__()
        # expected = textwrap.dedent(
        #     """\
        #     array([[ True, False],
        #            [False,  True],
        #            [False, False]])"""
        # )
        # self.assertEqual(expected, result)
        #
        # series = pd.Series(s)
        # result = repr(series)
        # expected = textwrap.dedent(
        #     """\
        #     0   [ True False]
        #     1   [False  True]
        #     2   [False False]
        #     dtype: TensorType"""
        # )
        # # self.assertEqual(expected, result)
        # print(f"***{result}***")

    def test_to_str(self):
        x = np.array([[1, 2], [3, 4], [5, 6]])
        expected = "[[1 2]\n [3 4]\n [5 6]]"
        s = TensorArray(x)
        result = str(s)
        self.assertEqual(expected, result)

        # The following currently doesn't work, due to
        # https://github.com/pandas-dev/pandas/issues/33770
        # TODO: Re-enable when a version of Pandas with a fix is released.
        # y = np.array([[True, False], [False, True], [False, False]])
        # s = TensorArray(y)
        # result = str(s)
        # expected = textwrap.dedent(
        #     """\
        #     [[ True False]
        #      [False  True]
        #      [False False]]"""
        # )
        # self.assertEqual(expected, result)

    def test_concat(self):
        x = np.arange(6).reshape((3, 2))
        y = np.arange(6, 12).reshape((3, 2))
        x_arr = TensorArray(x)
        y_arr = TensorArray(y)
        concat_arr = TensorArray._concat_same_type((x_arr, y_arr))
        result = str(concat_arr)
        self.assertEqual(
            result,
            textwrap.dedent(
                """\
                [[ 0  1]
                 [ 2  3]
                 [ 4  5]
                 [ 6  7]
                 [ 8  9]
                 [10 11]]"""
            ),
        )

    def test_series_to_str(self):
        x = np.arange(50).reshape((10, 5))
        a = TensorArray(x)
        s = pd.Series(a)
        result = s.to_string(max_rows=4)
        self.assertEqual(
            result,
            textwrap.dedent(
                """\
                0        [0 1 2 3 4]
                1        [5 6 7 8 9]
                          ...       
                8   [40 41 42 43 44]
                9   [45 46 47 48 49]"""
            ),
        )

    def test_slice(self):
        x = np.array([[1, 2], [3, 4], [5, 6]])
        s = TensorArray(x)

        result = s[1]
        self.assertTrue(isinstance(result, np.ndarray))
        expected = np.array([3, 4])
        npt.assert_array_equal(expected, result)

        result = s[1:3]
        self.assertTrue(isinstance(result, TensorArray))
        expected = np.array([[3, 4], [5, 6]])
        npt.assert_array_equal(expected, result.to_numpy())

    def test_bool_indexing(self):
        s = TensorArray([[1, 2], [3, 4]])

        result = s[[True, True]]
        self.assertTrue(isinstance(result, TensorArray))
        expected = np.array([[1, 2], [3, 4]])
        npt.assert_array_equal(result.to_numpy(), expected)

        result = s[[True, False]]
        self.assertTrue(isinstance(result, TensorArray))
        expected = np.array([[1, 2]])
        npt.assert_array_equal(result.to_numpy(), expected)

        result = s[[False, True]]
        self.assertTrue(isinstance(result, TensorArray))
        expected = np.array([[3, 4]])
        npt.assert_array_equal(result.to_numpy(), expected)

        result = s[[False, False]]
        self.assertTrue(isinstance(result, TensorArray))
        expected = np.empty((0, 2))
        npt.assert_array_equal(result.to_numpy(), expected)

    def test_asarray(self):
        x = np.array([[1, 2], [3, 4], [5, 6]])
        s = TensorArray(x)
        a = np.asarray(s)
        npt.assert_array_equal(x, a)
        npt.assert_array_equal(x, s.to_numpy())


class TensorArrayDataFrameTests(unittest.TestCase):
    def test_create(self):
        x = np.array([[1, 2], [3, 4], [5, 6]])
        s = TensorArray(x)
        df = pd.DataFrame({"i": list(range(len(x))), "tensor": s})
        self.assertEqual(len(df), len(x))

    def test_sum(self):
        keys = ["a", "a", "b", "c", "c", "c"]
        values = np.array([[1, 1]] * len(keys))
        df = pd.DataFrame({"key": keys, "value": TensorArray(values)})
        result_df = df.groupby("key").aggregate({"value": "sum"})
        self.assertEqual(
            repr(result_df),
            textwrap.dedent(
                """\
                      value
                key        
                a    [2, 2]
                b    [1, 1]
                c    [3, 3]"""
            ),
        )

        # 2D values
        values2 = np.array([[[1, 1], [1, 1]]] * len(keys))
        df2 = pd.DataFrame({"key": keys, "value": TensorArray(values2)})
        result2_df = df2.groupby("key").aggregate({"value": "sum"})
        self.assertEqual(
            repr(result2_df),
            textwrap.dedent(
                """\
                                value
                key                  
                a    [[2, 2], [2, 2]]
                b    [[1, 1], [1, 1]]
                c    [[3, 3], [3, 3]]"""
            ),
        )

    def test_bool_indexing_dataframe(self):
        s = TensorArray([[1, 2], [3, 4]])
        df = pd.DataFrame({
            "col1": s
        })
        result = df[[False, False]]
        self.assertTrue(isinstance(result, pd.DataFrame))
        self.assertEqual(len(result), 0)

        result = df[[True, True]]
        self.assertTrue(isinstance(result, pd.DataFrame))
        pd.testing.assert_frame_equal(result, df)

        result = df[[True, False]]
        self.assertTrue(isinstance(result, pd.DataFrame))
        self.assertEqual(len(result), 1)
        expected = df.iloc[[0]]
        pd.testing.assert_frame_equal(result, expected)

        result = df[[False, True]]
        self.assertTrue(isinstance(result, pd.DataFrame))
        self.assertEqual(len(result), 1)
        expected = df.iloc[[1]]
        pd.testing.assert_frame_equal(result, expected)

    def test_bool_indexing_series(self):
        s = pd.Series(TensorArray([[1, 2], [3, 4]]))
        result = s[[False, False]]
        self.assertTrue(isinstance(result, pd.Series))
        self.assertEqual(len(result), 0)

        result = s[[True, True]]
        self.assertTrue(isinstance(result, pd.Series))
        pd.testing.assert_series_equal(result, s)

        result = s[[True, False]]
        self.assertTrue(isinstance(result, pd.Series))
        self.assertEqual(len(result), 1)
        expected = s.iloc[[0]]
        pd.testing.assert_series_equal(result, expected)

        result = s[[False, True]]
        self.assertTrue(isinstance(result, pd.Series))
        self.assertEqual(len(result), 1)
        expected = s.iloc[[1]]
        pd.testing.assert_series_equal(result, expected)


class TensorArrayIOTests(unittest.TestCase):
    def test_feather(self):
        x = np.arange(10).reshape(5, 2)
        s = TensorArray(x)
        df = pd.DataFrame({"i": list(range(len(x))), "tensor": s})

        with tempfile.TemporaryDirectory() as dirpath:
            filename = os.path.join(dirpath, "tensor_array_test.feather")
            df.to_feather(filename)
            df_read = pd.read_feather(filename)
            pd.testing.assert_frame_equal(df, df_read)

    @unittest.skip("TODO: error when reading parquet back")
    def test_parquet(self):
        x = np.arange(10).reshape(5, 2)
        s = TensorArray(x)
        df = pd.DataFrame({"i": list(range(len(x))), "tensor": s})

        with tempfile.TemporaryDirectory() as dirpath:
            filename = os.path.join(dirpath, "tensor_array_test.parquet")
            df.to_parquet(filename)
            df_read = pd.read_parquet(filename)
            pd.testing.assert_frame_equal(df, df_read)

    def test_feather_chunked(self):
        import pyarrow as pa
        from pyarrow.feather import write_feather

        x = np.arange(10).reshape(5, 2)
        s = TensorArray(x)
        df1 = pd.DataFrame({"i": list(range(len(s))), "tensor": s})

        # Create a Table with 2 chunks
        table1 = pa.Table.from_pandas(df1)
        df2 = df1.copy()
        df2["tensor"] = df2["tensor"] * 10
        table2 = pa.Table.from_pandas(df2)
        table = pa.concat_tables([table1, table2])
        self.assertEqual(table.column("tensor").num_chunks, 2)

        # Write table to feather and read back as a DataFrame
        with tempfile.TemporaryDirectory() as dirpath:
            filename = os.path.join(dirpath, "tensor_array_chunked_test.feather")
            write_feather(table, filename)
            df_read = pd.read_feather(filename)
            df_expected = pd.concat([df1, df2]).reset_index(drop=True)
            pd.testing.assert_frame_equal(df_expected, df_read)

    def test_feather_auto_chunked(self):
        import pyarrow as pa
        from pyarrow.feather import read_table, write_feather

        x = np.arange(2048).reshape(1024, 2)
        s = TensorArray(x)
        df = pd.DataFrame({"i": list(range(len(s))), "tensor": s})

        table = pa.Table.from_pandas(df)

        # Write table to feather and read back as a DataFrame
        with tempfile.TemporaryDirectory() as dirpath:
            filename = os.path.join(dirpath, "tensor_array_chunked_test.feather")
            write_feather(table, filename, chunksize=512)
            table = read_table(filename)
            self.assertGreaterEqual(table.column("tensor").num_chunks, 2)
            df_read = pd.read_feather(filename)
            pd.testing.assert_frame_equal(df, df_read)
