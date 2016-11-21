from setuptools import setup, find_packages

setup(
        name='data_analysis',
        version='0.0.1',
        url='www.github.com/benhoff/data-analysis',
        license='BSD',
        author='Ben Hoff',
        packages=find_packages(),
        install_requires=['pyqt5',
                          'pandas',
                          'sqlalchemy',
                          'nltk',
                          'numpy',
                          'jupyter',
                          'tweepy'],

        entry_points={},
        extras_require={'dev': ['flake8',]},
        )
