import csv


class Opening:
    openings = dict()
    fav = dict()

    @classmethod
    def collect_data(cls):
        header = True
        with open('openings.csv') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            
            for row in csv_reader:
                if header:
                    header = False
                else:
                    cls.openings[row[1]] = row[3]
    
    @classmethod
    def get(cls, name):
        try:
            moves = cls.openings[name].split(' ')
            return moves
        except KeyError:
            return []
    
    @classmethod
    def set_favorite(cls, user, opening):
        cls.fav[user] = opening
    
    @classmethod
    def get_favorite(cls, user):
        try:
            return cls.fav[user]
        except KeyError:
            return None