#!/usr/bin/env python

# Copyright JS Foundation and other contributors, http://js.foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function
from settings import PROJECT_DIR
from unicode_c_source import Source

import argparse
import csv
import itertools
import os
import sys
import warnings

CONVERSIONS_C_SOURCE = os.path.join(PROJECT_DIR, 'jerry-core/lit/lit-unicode-conversions.inc.h')


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--unicode-data',
                        metavar='FILE',
                        action='store',
                        required=True,
                        help='specify the unicode data file')

    parser.add_argument('--special-casing',
                        metavar='FILE',
                        action='store',
                        required=True,
                        help='specify the special casing file')

    parser.add_argument('--c-source',
                        metavar='FILE',
                        action='store',
                        default=CONVERSIONS_C_SOURCE,
                        help='specify the output c source for the conversion tables (default: %(default)s)')

    script_args = parser.parse_args()

    if not os.path.isfile(script_args.unicode_data) or not os.access(script_args.unicode_data, os.R_OK):
        print('The %s file is missing or not readable!' % script_args.unicode_data)
        sys.exit(1)

    if not os.path.isfile(script_args.special_casing) or not os.access(script_args.special_casing, os.R_OK):
        print('The %s file is missing or not readable!' % script_args.special_casing)
        sys.exit(1)

    conv_tables = ConversionTables(script_args.unicode_data, script_args.special_casing)

    character_case_ranges = conv_tables.get_character_case_ranges()
    character_pair_ranges = conv_tables.get_character_pair_ranges()
    character_pairs = conv_tables.get_character_pairs()
    upper_case_special_ranges = conv_tables.get_upper_case_special_ranges()
    lower_case_ranges = conv_tables.get_lower_case_ranges()
    lower_case_conversions = conv_tables.get_lower_case_conversions()
    upper_case_conversions = conv_tables.get_upper_case_conversions()

    c_source = Source(script_args.c_source)

    unicode_file = os.path.basename(script_args.unicode_data)
    spec_casing_file = os.path.basename(script_args.special_casing)

    header_completion = ["/* This file is automatically generated by the %s script" % os.path.basename(__file__),
                         " * from %s and %s files. Do not edit! */" % (unicode_file, spec_casing_file),
                         ""]

    c_source.complete_header("\n".join(header_completion))

    c_source.add_table(character_case_ranges[0],
                       "character_case_ranges",
                       "uint16_t",
                       ("/* Contains start points of character case ranges "
                        "(these are bidirectional conversions). */"))

    c_source.add_table(character_case_ranges[1],
                       "character_case_range_lengths",
                       "uint8_t",
                       "/* Interval lengths of start points in `character_case_ranges` table. */")

    c_source.add_table(character_pair_ranges[0],
                       "character_pair_ranges",
                       "uint16_t",
                       "/* Contains the start points of bidirectional conversion ranges. */")

    c_source.add_table(character_pair_ranges[1],
                       "character_pair_range_lengths",
                       "uint8_t",
                       "/* Interval lengths of start points in `character_pair_ranges` table. */")

    c_source.add_table(character_pairs,
                       "character_pairs",
                       "uint16_t",
                       "/* Contains lower/upper case bidirectional conversion pairs. */")

    c_source.add_table(upper_case_special_ranges[0],
                       "upper_case_special_ranges",
                       "uint16_t",
                       ("/* Contains start points of one-to-two uppercase ranges where the second character\n"
                        " * is always the same.\n"
                        " */"))

    c_source.add_table(upper_case_special_ranges[1],
                       "upper_case_special_range_lengths",
                       "uint8_t",
                       "/* Interval lengths for start points in `upper_case_special_ranges` table. */")

    c_source.add_table(lower_case_ranges[0],
                       "lower_case_ranges",
                       "uint16_t",
                       "/* Contains start points of lowercase ranges. */")

    c_source.add_table(lower_case_ranges[1],
                       "lower_case_range_lengths",
                       "uint8_t",
                       "/* Interval lengths for start points in `lower_case_ranges` table. */")

    c_source.add_table(lower_case_conversions[0],
                       "lower_case_conversions",
                       "uint16_t",
                       ("/* The remaining lowercase conversions. The lowercase variant can "
                        "be one-to-three character long. */"))

    c_source.add_table(lower_case_conversions[1],
                       "lower_case_conversion_counters",
                       "uint8_t",
                       "/* Number of one-to-one, one-to-two, and one-to-three lowercase conversions. */")

    c_source.add_table(upper_case_conversions[0],
                       "upper_case_conversions",
                       "uint16_t",
                       ("/* The remaining uppercase conversions. The uppercase variant can "
                        "be one-to-three character long. */"))

    c_source.add_table(upper_case_conversions[1],
                       "upper_case_conversion_counters",
                       "uint8_t",
                       "/* Number of one-to-one, one-to-two, and one-to-three uppercase conversions. */")

    c_source.generate()


class ConversionTables(object):
    def __init__(self, unicode_data_file, special_casing_file):
        """
        Read the corresponding unicode values of lower and upper case letters and store these in tables

        :param unicode_data_file: Contains the default case mappings (one-to-one mappings).
        :param special_casing_file: Contains additional informative case mappings that are either not one-to-one
                                    or which are context-sensitive.
        """

        case_mappings = read_case_mappings(unicode_data_file, special_casing_file)
        lower_case = case_mappings[0]
        upper_case = case_mappings[1]

        self.__character_case_ranges = extract_ranges(lower_case, upper_case)
        self.__character_pair_ranges = extract_character_pair_ranges(lower_case, upper_case)
        self.__character_pairs = extract_character_pairs(lower_case, upper_case)
        self.__upper_case_special_ranges = extract_special_ranges(upper_case)
        self.__lower_case_ranges = extract_ranges(lower_case)
        self.__lower_case_conversions = extract_conversions(lower_case)
        self.__upper_case_conversions = extract_conversions(upper_case)

        if lower_case:
            warnings.warn('Not all elements extracted from the lowercase table!')
        if upper_case:
            warnings.warn('Not all elements extracted from the uppercase table!')

    def get_character_case_ranges(self):
        return self.__character_case_ranges

    def get_character_pair_ranges(self):
        return self.__character_pair_ranges

    def get_character_pairs(self):
        return self.__character_pairs

    def get_upper_case_special_ranges(self):
        return self.__upper_case_special_ranges

    def get_lower_case_ranges(self):
        return self.__lower_case_ranges

    def get_lower_case_conversions(self):
        return self.__lower_case_conversions

    def get_upper_case_conversions(self):
        return self.__upper_case_conversions


def parse_unicode_sequence(raw_data):
    """
    Parse unicode sequence from raw data.

    :param raw_data: Contains the unicode sequence which needs to parse.
    :return: The parsed unicode sequence.
    """

    result = ''

    for unicode_char in raw_data.split(' '):
        if unicode_char == '':
            continue

        # Convert it to unicode code point (from hex value without 0x prefix)
        hex_val = int(unicode_char, 16)
        try:
            result += unichr(hex_val)
        except NameError:
            result += chr(hex_val)

    return result


def read_case_mappings(unicode_data_file, special_casing_file):
    """
    Read the corresponding unicode values of lower and upper case letters and store these in tables.

    :param unicode_data_file: Contains the default case mappings (one-to-one mappings).
    :param special_casing_file: Contains additional informative case mappings that are either not one-to-one
                                or which are context-sensitive.
    :return: Upper and lower case mappings.
    """

    lower_case_mapping = {}
    upper_case_mapping = {}

    # Add one-to-one mappings
    with open(unicode_data_file) as unicode_data:
        unicode_data_reader = csv.reader(unicode_data, delimiter=';')

        for line in unicode_data_reader:
            letter_id = int(line[0], 16)

            # Skip supplementary planes and ascii chars
            if letter_id >= 0x10000 or letter_id < 128:
                continue

            capital_letter = line[12]
            small_letter = line[13]

            if capital_letter:
                upper_case_mapping[letter_id] = parse_unicode_sequence(capital_letter)

            if small_letter:
                lower_case_mapping[letter_id] = parse_unicode_sequence(small_letter)

    # Update the conversion tables with the special cases
    with open(special_casing_file) as special_casing:
        special_casing_reader = csv.reader(special_casing, delimiter=';')

        for line in special_casing_reader:
            # Skip comment sections and empty lines
            if not line or line[0].startswith('#'):
                continue

            # Replace '#' character with empty string
            for idx, i in enumerate(line):
                if i.find('#') >= 0:
                    line[idx] = ''

            letter_id = int(line[0], 16)
            condition_list = line[4]

            # Skip supplementary planes, ascii chars, and condition_list
            if letter_id >= 0x10000 or letter_id < 128 or condition_list:
                continue

            small_letter = parse_unicode_sequence(line[1])
            capital_letter = parse_unicode_sequence(line[3])

            lower_case_mapping[letter_id] = small_letter
            upper_case_mapping[letter_id] = capital_letter

    return lower_case_mapping, upper_case_mapping


def extract_ranges(letter_case, reverse_letter_case=None):
    """
    Extract ranges from case mappings
    (the second param is optional, if it's not empty, a range will contains bidirectional conversions only).

    :param letter_id: An integer, representing the unicode code point of the character.
    :param letter_case: case mappings dictionary which contains the conversions.
    :param reverse_letter_case: Comparable case mapping table which contains the return direction of the conversion.
    :return: A table with the start points and their mapped value, and another table with the lengths of the ranges.
    """

    in_range = False
    range_position = -1
    ranges = []
    range_lengths = []

    for letter_id in sorted(letter_case.keys()):
        prev_letter_id = letter_id - 1

        # One-way conversions
        if reverse_letter_case is None:
            if len(letter_case[letter_id]) > 1:
                in_range = False
                continue

            if prev_letter_id not in letter_case or len(letter_case[prev_letter_id]) > 1:
                in_range = False
                continue

        # Two way conversions
        else:
            if not is_bidirectional_conversion(letter_id, letter_case, reverse_letter_case):
                in_range = False
                continue

            if not is_bidirectional_conversion(prev_letter_id, letter_case, reverse_letter_case):
                in_range = False
                continue

        conv_distance = calculate_conversion_distance(letter_case, letter_id)
        prev_conv_distance = calculate_conversion_distance(letter_case, prev_letter_id)

        if conv_distance != prev_conv_distance:
            in_range = False
            continue

        if in_range:
            range_lengths[range_position] += 1
        else:
            in_range = True
            range_position += 1

            # Add the start point of the range and its mapped value
            ranges.extend([prev_letter_id, ord(letter_case[prev_letter_id])])
            range_lengths.append(2)

    # Remove all ranges from the case mapping table.
    for idx in range(0, len(ranges), 2):
        range_length = range_lengths[idx // 2]

        for incr in range(range_length):
            del letter_case[ranges[idx] + incr]
            if reverse_letter_case is not None:
                del reverse_letter_case[ranges[idx + 1] + incr]

    return ranges, range_lengths


def extract_character_pair_ranges(letter_case, reverse_letter_case):
    """
    Extract two or more character pairs from the case mapping tables.

    :param letter_case: case mappings dictionary which contains the conversions.
    :param reverse_letter_case: Comparable case mapping table which contains the return direction of the conversion.
    :return: A table with the start points, and another table with the lengths of the ranges.
    """

    start_points = []
    lengths = []
    in_range = False
    element_counter = -1

    for letter_id in sorted(letter_case.keys()):
        # Only extract character pairs
        if not is_bidirectional_conversion(letter_id, letter_case, reverse_letter_case):
            in_range = False
            continue

        if ord(letter_case[letter_id]) == letter_id + 1:
            prev_letter_id = letter_id - 2

            if not is_bidirectional_conversion(prev_letter_id, letter_case, reverse_letter_case):
                in_range = False

            if in_range:
                lengths[element_counter] += 2
            else:
                element_counter += 1
                start_points.append(letter_id)
                lengths.append(2)
                in_range = True

        else:
            in_range = False

    # Remove all founded case mapping from the conversion tables after the scanning method
    for idx in range(len(start_points)):
        letter_id = start_points[idx]
        conv_length = lengths[idx]

        for incr in range(0, conv_length, 2):
            del letter_case[letter_id + incr]
            del reverse_letter_case[letter_id + 1 + incr]

    return start_points, lengths


def extract_character_pairs(letter_case, reverse_letter_case):
    """
    Extract character pairs. Check that two unicode value are also a mapping value of each other.

    :param letter_case: case mappings dictionary which contains the conversions.
    :param reverse_letter_case: Comparable case mapping table which contains the return direction of the conversion.
    :return: A table with character pairs.
    """

    character_pairs = []

    for letter_id in sorted(letter_case.keys()):
        if is_bidirectional_conversion(letter_id, letter_case, reverse_letter_case):
            mapped_value = letter_case[letter_id]
            character_pairs.extend([letter_id, ord(mapped_value)])

            # Remove character pairs from case mapping tables
            del letter_case[letter_id]
            del reverse_letter_case[ord(mapped_value)]

    return character_pairs


def extract_special_ranges(letter_case):
    """
    Extract special ranges. It contains start points of one-to-two letter case ranges
    where the second character is always the same.

    :param letter_case: case mappings dictionary which contains the conversions.

    :return: A table with the start points and their mapped values, and a table with the lengths of the ranges.
    """

    special_ranges = []
    special_range_lengths = []

    range_position = -1

    for letter_id in sorted(letter_case.keys()):
        mapped_value = letter_case[letter_id]

        if len(mapped_value) != 2:
            continue

        prev_letter_id = letter_id - 1

        if prev_letter_id not in letter_case:
            in_range = False
            continue

        prev_mapped_value = letter_case[prev_letter_id]

        if len(prev_mapped_value) != 2:
            continue

        if prev_mapped_value[1] != mapped_value[1]:
            continue

        if (ord(prev_mapped_value[0]) - prev_letter_id) != (ord(mapped_value[0]) - letter_id):
            in_range = False
            continue

        if in_range:
            special_range_lengths[range_position] += 1
        else:
            range_position += 1
            in_range = True

            special_ranges.extend([prev_letter_id, ord(prev_mapped_value[0]), ord(prev_mapped_value[1])])
            special_range_lengths.append(1)

    # Remove special ranges from the conversion table
    for idx in range(0, len(special_ranges), 3):
        range_length = special_range_lengths[idx // 3]
        letter_id = special_ranges[idx]

        for incr in range(range_length):
            del letter_case[special_ranges[idx] + incr]

    return special_ranges, special_range_lengths


def extract_conversions(letter_case):
    """
    Extract conversions. It provide the full (or remained) case mappings from the table.
    The counter table contains the information of how much one-to-one, one-to-two or one-to-three mappings
    exists successively in the conversion table.

    :return: A table with conversions, and a table with counters.
    """

    unicodes = [[], [], []]
    unicode_lengths = [0, 0, 0]

    # 1 to 1 byte
    for letter_id in sorted(letter_case.keys()):
        mapped_value = letter_case[letter_id]

        if len(mapped_value) != 1:
            continue

        unicodes[0].extend([letter_id, ord(mapped_value)])
        del letter_case[letter_id]

    # 1 to 2 bytes
    for letter_id in sorted(letter_case.keys()):
        mapped_value = letter_case[letter_id]

        if len(mapped_value) != 2:
            continue

        unicodes[1].extend([letter_id, ord(mapped_value[0]), ord(mapped_value[1])])
        del letter_case[letter_id]

    # 1 to 3 bytes
    for letter_id in sorted(letter_case.keys()):
        mapped_value = letter_case[letter_id]

        if len(mapped_value) != 3:
            continue

        unicodes[2].extend([letter_id, ord(mapped_value[0]), ord(mapped_value[1]), ord(mapped_value[2])])
        del letter_case[letter_id]

    unicode_lengths = [int(len(unicodes[0]) / 2), int(len(unicodes[1]) / 3), int(len(unicodes[2]) / 4)]

    return list(itertools.chain.from_iterable(unicodes)), unicode_lengths


def is_bidirectional_conversion(letter_id, letter_case, reverse_letter_case):
    """
    Check that two unicode value are also a mapping value of each other.

    :param letter_id: An integer, representing the unicode code point of the character.
    :param other_case_mapping: Comparable case mapping table which possible contains
                               the return direction of the conversion.
    :return: True, if it's a reverible conversion, false otherwise.
    """

    if letter_id not in letter_case:
        return False

    # Check one-to-one mapping
    mapped_value = letter_case[letter_id]
    if len(mapped_value) > 1:
        return False

    # Check two way conversions
    mapped_value_id = ord(mapped_value)

    if mapped_value_id not in reverse_letter_case or len(reverse_letter_case[mapped_value_id]) > 1:
        return False

    if ord(reverse_letter_case[mapped_value_id]) != letter_id:
        return False

    return True


def calculate_conversion_distance(letter_case, letter_id):
    """
    Calculate the distance between the unicode character and its mapped value
    (only needs and works with one-to-one mappings).

    :param letter_case: case mappings dictionary which contains the conversions.
    :param letter_id: An integer, representing the unicode code point of the character.
    :return: The conversion distance.
    """

    if letter_id not in letter_case or len(letter_case[letter_id]) > 1:
        return None

    return ord(letter_case[letter_id]) - letter_id


if __name__ == "__main__":
    main()
