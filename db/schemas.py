from post_orm import Column, Table


class ConversationHistory(Table):
    timestamp = Column(str)
    question = Column(str)
    answer = Column(str)

class Weather(Table):
    datestamp = Column(str)
    location = Column(str)
    forecast = Column(str)