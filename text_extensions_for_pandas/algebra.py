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

################################################################################
# algebra.py
#
# Span manipulation functions from text_extensions_for_pandas

from typing import *

import numpy as np
import pandas as pd
import regex

# Internal imports
from text_extensions_for_pandas.char_span import CharSpan, CharSpanType,\
    CharSpanArray
from text_extensions_for_pandas.token_span import TokenSpan, TokenSpanType,\
    TokenSpanArray


def extract_dict(tokens: Union[CharSpanArray, pd.Series],
                 dictionary: pd.DataFrame,
                 output_col_name: str = "match"):
    """
    Identify all matches of a dictionary on a sequence of tokens.

    :param tokens: `CharSpanArray` of token information, optionally wrapped in a
    `pd.Series`.

    :param dictionary: The dictionary to match, encoded as a `pd.DataFrame` in
    the format returned by `load_dict()`

    :param output_col_name: (optional) name of column of matching spans in the
    returned DataFrame

    :return: a single-column DataFrame of token ID spans of dictionary matches
    """
    # Box tokens into a pd.Series if not already boxed.
    if isinstance(tokens, CharSpanArray):
        tokens = pd.Series(tokens)

    # Wrap the important parts of the tokens series in a temporary dataframe.
    toks_tmp = pd.DataFrame({
        "token_id": tokens.index,
        "normalized_text": tokens.values.normalized_covered_text
    })

    # Start by matching the first token.
    matches = pd.merge(dictionary, toks_tmp,
                       left_on="toks_0", right_on="normalized_text")
    matches.rename(columns={"token_id": "begin_token_id"}, inplace=True)
    matches_col_names = list(matches.columns)  # We'll need this later

    # Check against remaining elements of matching dictionary entries and
    # accumulate the full set of matches as a list of IntervalIndexes
    begins_list = []
    ends_list = []
    max_entry_len = len(dictionary.columns)
    for match_len in range(1, max_entry_len):
        # print("Match len: {}".format(match_len))
        # Find matches of length match_len. Dictionary entries of this length
        # will have None in the column "toks_<match_len>".
        match_locs = pd.isna(matches["toks_{}".format(match_len)])
        # print("Completed matches:\n{}".format(matches[match_locs]))
        match_begins = matches[match_locs]["begin_token_id"].to_numpy()
        match_ends = match_begins + match_len
        begins_list.append(match_begins)
        ends_list.append(match_ends)

        # For the remaining partial matches against longer dictionary entries,
        # check the next token by merging with the tokens dataframe.
        potential_matches = matches[~match_locs].copy()
        # print("Raw potential matches:\n{}".format(potential_matches))
        potential_matches.drop("normalized_text", axis=1, inplace=True)
        potential_matches["next_token_id"] = potential_matches[
                                                 "begin_token_id"] + match_len
        potential_matches = pd.merge(potential_matches, toks_tmp,
                                     left_on="next_token_id",
                                     right_on="token_id")
        # print("Filtered potential matches:\n{}".format(potential_matches))
        potential_matches = potential_matches[
            potential_matches["normalized_text"] == potential_matches[
                "toks_{}".format(match_len)]]
        # The result of the join has some extra columns that we don't need.
        matches = potential_matches[matches_col_names]
    # Gather together all the sets of matches and wrap in a dataframe.
    begins = np.concatenate(begins_list)
    ends = np.concatenate(ends_list)
    return pd.DataFrame({output_col_name: TokenSpanArray(tokens.values,
                                                         begins, ends)})


def extract_regex_tok(
        tokens: Union[CharSpanArray, pd.Series],
        compiled_regex: regex.Regex,
        min_len=1,
        max_len=1,
        output_col_name: str = "match"):
    """
    Identify all (possibly overlapping) matches of a regular expression
    that start and end on token boundaries.

    :param tokens: `CharSpanArray` of token information, optionally wrapped in a
    `pd.Series`.

    :param compiled_regex: Regular expression to evaluate.

    :param min_len: Minimum match length in tokens

    :param max_len: Maximum match length (inclusive) in tokens

    :param output_col_name: (optional) name of column of matching spans in the
    returned DataFrame

    :returns: A single-column DataFrame containing a span for each match of the
    regex.
    """
    if isinstance(tokens, CharSpanArray):
        tokens = pd.Series(tokens)

    num_tokens = len(tokens.values)
    matches_regex_f = np.vectorize(lambda s: compiled_regex.fullmatch(s)
                                             is not None)

    # The built-in regex functionality of Pandas/Python does not have
    # an optimized single-pass RegexTok, so generate all the places
    # where there might be a match and run them through regex.fullmatch().
    # Note that this approach is asymptotically inefficient if max_len is large.
    # TODO: Performance tuning for both small and large max_len
    matches_list = []
    for cur_len in range(min_len, max_len + 1):
        window_begin_toks = np.arange(0, num_tokens - cur_len + 1)
        window_end_toks = window_begin_toks + cur_len

        window_tok_spans = TokenSpanArray(tokens.values, window_begin_toks,
                                          window_end_toks)
        matches_list.append(pd.Series(
            window_tok_spans[matches_regex_f(window_tok_spans.covered_text)]
        ))
    return pd.DataFrame({output_col_name: pd.concat(matches_list)})


def adjacent_join(first_series: pd.Series,
                  second_series: pd.Series,
                  first_name: str = "first",
                  second_name: str = "second",
                  min_gap: int = 0,
                  max_gap: int = 0):
    """
    Compute the join of two series of spans, where a pair of spans is
    considered to match if they are adjacent to each other in the text.

    :param first_series: Spans that appear earlier. dtype must be TokenSpan.

    :param second_series: Spans that come after. dtype must be TokenSpan.

    :param first_name: Name to give the column in the returned dataframe that
    is derived from `first_series`.

    :param second_name: Column name for spans from `second_series` in the
    returned DataFrame.

    :param min_gap: Minimum number of spans allowed between matching pairs of
    spans, inclusive.

    :param max_gap: Maximum number of spans allowed between matching pairs of
    spans, inclusive.

    :returns: a new `pd.DataFrame` containing all pairs of spans that match
    the join predicate. Columns of the DataFrame will be named according
    to the `first_name` and `second_name` arguments.
    """
    # For now we always make the first series the outer.
    # TODO: Make the larger series the outer and adjust the join logic
    # below accordingly.
    outer = pd.DataFrame({
        "outer_span": first_series,
        "outer_end": first_series.values.end_token
    })

    # Inner series gets replicated for every possible offset so we can use
    # Pandas' high-performance equijoin
    inner_span_list = [second_series] * (max_gap - min_gap + 1)
    outer_end_list = [
        # Join predicate: outer_span = inner_span.begin + gap
        second_series.values.begin_token + gap
        for gap in range(min_gap, max_gap + 1)
    ]
    inner = pd.DataFrame({
        "inner_span": pd.concat(inner_span_list),
        "outer_end": np.concatenate(outer_end_list)
    })
    joined = outer.merge(inner)

    # Now we have a DataFrame with the schema
    # [outer_span, outer_end, inner_span]
    return pd.DataFrame({
        first_name: joined["outer_span"],
        second_name: joined["inner_span"]
    })


def combine_spans(series1: pd.Series, series2: pd.Series):
    """
    :param series1: A series backed by a TokenSpanArray
    :param series2: A series backed by a TokenSpanArray
    :return: A new series (also backed by a TokenSpanArray) of spans
        containing shortest span that completely covers both input spans.
    """
    spans1 = TokenSpanArray.make_array(series1)
    spans2 = TokenSpanArray.make_array(series2)
    # TODO: Raise an error if any span in series1 comes after the corresponding
    #  span in series2
    # TODO: Raise an error if series1.tokens != series2.tokens
    return pd.Series(TokenSpanArray(
        spans1.tokens, spans1.begin_token, spans2.end_token
    ))


def combine_agg(arg):
    """
    Aggregation function that takes in a set of spans and returns the smallest
    single span that covers all of the input spans.

    To use as a Pandas aggregate:
    ```python
    my_dataframe.groupby([<columns>]).aggregate({<column>: pt.combine})
    ```

    To apply directly to a series of a span type:
    ```python
    pt.combine(my_series)
    pt.combine(my_series.values)
    ```



    :param arg: A DataFrame, Series, or Iterable of `CharSpan` or `TokenSpan`
    objects.
    ```
    """
    # Massage the input into begin and end Numpy arrays and optional tokens
    if isinstance(arg, pd.Series):
        if isinstance(arg.dtype, TokenSpanType):
            spans = arg.values
            return TokenSpan(spans.tokens, np.min(spans.begin_token),
                             np.max(spans.end_token))
        elif isinstance(arg.dtype, CharSpanType):
            spans = arg.values
            return CharSpan(spans.target_text, np.min(spans.begin),
                            np.max(spans.end))
        else:
            raise ValueError(f"Unexpected series dtype {arg.dtype}")
    elif isinstance(arg, pd.DataFrame):
        raise NotImplementedError("DataFrame input not yet implemented")
    elif isinstance(arg, Iterable):
        raise NotImplementedError("Iterable input not yet implemented")
    else:
        raise ValueError(f"Unexpected input type {type(arg)}")


def lemmatize(spans: Union[pd.Series, TokenSpanArray, Iterable[TokenSpan]],
              token_features: pd.DataFrame,
              lemma_col_name: str = "lemma") -> List[str]:
    """
    Convert spans to their normal form using lemma information in a token
    features table.

    :param spans: Spans to be normalized. Each may represent zero or more
    tokens.

    :param token_features: Dataframe of token metadata. Index must be aligned
    with the token indices in `spans`.

    :param lemma_col_name: Optional custom name for the dataframe column
    containing the lemmatized form of each token.

    :return: A list containing normalized versions of the tokens
    in `spans`, with each token separated by single space character.
    """
    spans = TokenSpanArray.make_array(spans)
    ret = []  # Type: List[str]
    # TODO: Vectorize this loop
    for i in range(len(spans)):
        lemmas = token_features[lemma_col_name][
                 spans.begin_token[i]:spans.end_token[i]
                 ]
        ret.append(" ".join(lemmas))
    return ret