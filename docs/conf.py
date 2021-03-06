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
import sys
sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------

project = 'Text Extensions for Pandas'
copyright = '2020, IBM'
author = 'IBM'

# The full version, including alpha/beta/rc tags
release = '0.0.1'


# -- General configuration ---------------------------------------------------

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.coverage', 'sphinx.ext.napoleon', 
                'sphinx.ext.autosummary', 'sphinx.ext.intersphinx', 
                ]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']






# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.


exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store','text_extensions_for_pandas.util.rst']

#look through files in this directory that include `test_` in their name. 
# add them to the exclude_patterns list 
for filename in os.listdir():
    if ".test_" in filename:
        exclude_patterns.append(filename)


# -- Options for HTML output -------------------------------------------------

html_theme = 'nature'

html_static_path = ['_static']



