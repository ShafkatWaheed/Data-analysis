from tweepy.streaming import StreamListener


# TODO: add a way to tap running to false to perform country analysis
class StripListener(StreamListener):
    def __init__(self,
                 language: 'data_analysis.sentiment.Language'):

        self.analysis_signal = self._language.analysis_signal
        self._language = language
        self.running = True

    def on_data(self, data):
        data = json.loads(data)
        if 'in_reply_to_status_id' in data:
            if data['coordinates'] is not None:
                text = _get_text_cleaned(data)
                # Don't ask questions
                coords = data['coordinates']['coordinates']

                self._language.store_tweet(coords, text)

        if not self.running:
            return False
