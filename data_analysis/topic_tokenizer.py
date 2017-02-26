import re
import string

from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
from nltk.tokenize.casual import TweetTokenizer


class TopicTokenizer(TweetTokenizer):
    STOP = set(stopwords.words('english'))
    def __init__(self,
                 preserve_case=False,
                 reduce_len=True,
                 remove_url=True,
                 transform_handles=True,
                 stem_words=True):

        super().__init__(preserve_case,
                         reduce_len,
                         False)

        self.remove_url = remove_url
        self.transform_handles = transform_handles
        self.stem_words = stem_words
        self._stemmer = SnowballStemmer('english')
        self.STOP.update(('...', '…', '..', '‘', '’', 'rt', '–', '—'
            '1','2','3','4','5','6','7','8','9', '10', '11', '12', "i'll", 'ill', 'that', "you'r", 'ur', 'u', 'lol', 'one', "don't", "i'm", 'lmao', 'omg', 'im', "you're", 'oh', 'im', 'yall', "y'all", "you'll", 'that', 'didnt', "didn't", 'idk', "i've", 'w', "you're", 'ok', "isn't", "she's", "it's", "who's", "he's", "that's", "thats'", "what's", "there's", "whats'", "thats'", "here's", "how's", "others", "one's", '😂'))

        # https://github.com/nltk/nltk/blob/develop/nltk/tokenize/casual.py#L327
        self.twitter_handle_re = re.compile(r"(?<![A-Za-z0-9_!@#\$%&*])@(([A-Za-z0-9_]){20}(?!@))|(?<![A-Za-z0-9_!@#\$%&*])@(([A-Za-z0-9_]){1,19})(?![A-Za-z0-9_]*@)")

        # https://gist.github.com/uogbuji/705383
        self.url_re = re.compile(r'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')

    def fix_handles(self, text):
        return self.twitter_handle_re.sub('', text)

    def handle_urls(self, text):
        return self.url_re.sub('', text)

    def stem(self, words):
        stemmed = [self._stemmer.stem(word)
                   for word in words
                   if not (word in string.punctuation 
                           or word in self.STOP)]

        return stemmed

    def tokenize(self, text):
        # Text preprocessing
        if self.remove_url:
            text = self.handle_urls(text)
        if self.transform_handles:
            text = self.fix_handles(text)

        words = super().tokenize(text)
        if self.stem_words:
            words = self.stem(words)

        return words
    
