from bs4 import BeautifulSoup
from imdb import Cinemagoer
import streamlit as st
import pandas as pd
import requests


cg = Cinemagoer()


# API does not return the total amount of connections due to a button
# that needs to be clicked to 'see more' connections
@st.cache_resource(show_spinner=False)
def get_num_connections(tconst, connection_type):

    url_user = 'https://www.imdb.com/title/{}/movieconnections/'.format(tconst)
    user_agent = {'User-agent': 'Mozilla/5.0'}
    r = requests.get(url_user, headers=user_agent)
    soup = BeautifulSoup(r.content, 'html5lib')

    if connection_type == 'followed by':
        connection_type = 'followed_by' 

    connection = soup.find('option', {'value':'#'+connection_type})
    if connection is None:
        return 0
    
    txt = connection.text
    num_connections = int(txt[txt.find('(')+1:txt.find(')')])

    return num_connections



# Find connections of a given title
@st.cache_resource(show_spinner=False)
def find_title_connections(tconst, connection_type):

    '''
    Given a title identifier (tconst), find its prequel(s) and sequels(s).

    tconst: string denoting title ID
    connection_type: string, one of 'follows' or 'followed by'
    '''

    title = cg.get_movie(tconst[2:], info='connections') # ALTERNATIVE:ia.get_movie_connections(tconst[2:])
    
    '''
    title.items() FORMAT
    [
        ('connections', {
            'edited into': [<Movie id:0092635[http] title:_Bellissimo: Immagini del cinema italiano (1985)_>, <Movie id:0493428[http] title:_Instructions for a Light and Sound Machine (Short 2005) (None)_>],
            'featured in': [<Movie id:0084488[http] title:_Permanent Vacation (1980)_>, <Movie id:14783060[http] title:_"At the Movies" Back in the Saddle Again: The Rebirth of the Western (TV Episode 1985) (????)_>, <Movie id:0125090[http] title:_"Fejezetek a film történetéböl" Amerikai filmtípusok - A western (TV Episode 1989) (????)_>, <Movie id:0638742[http] title:_"MacGyver" MacGyver's Women (TV Episode 1990) (????)_>, <Movie id:0211493[http] title:_MGM/UA Home Video Laserdisc Sampler (Video 1990) (None)_>], 
            'follows': [<Movie id:0058461[http] title:_A Fistful of Dollars (1964)_>, <Movie id:0059578[http] title:_For a Few Dollars More (1965)_>], 
            'referenced in': [<Movie id:0062429[http] title:_Any Gun Can Play (1967)_>, <Movie id:0064860[http] title:_Ace High (1968)_>, <Movie id:0415364[http] title:_Western, Italian Style (TV Movie 1968) (None)_>, <Movie id:0063740[http] title:_Cemetery Without Crosses (1969)_>, <Movie id:0062437[http] title:_Una vez al año ser hippy no hace daño (1969)_>], 
            'references': [<Movie id:0015881[http] title:_Greed (1924)_>, <Movie id:0015624[http] title:_The Big Parade (1925)_>, <Movie id:0017925[http] title:_The General (1926)_>, <Movie id:0022286[http] title:_The Public Enemy (1931)_>, <Movie id:0031381[http] title:_Gone with the Wind (1939)_>], 
            'remade as': [<Movie id:0313588[http] title:_Seytan Tirnagi (1972)_>, <Movie id:0109959[http] title:_Gunmen (1993)_>], 
            'spoofed in': [<Movie id:0155009[http] title:_For a Few Dollars Less (1966)_>, <Movie id:0122398[http] title:_The Handsome, the Ugly, and the Stupid (1967)_>, <Movie id:0587573[http] title:_"Get Smart" Tequila Mockingbird (TV Episode 1969) (????)_>, <Movie id:0192081[http] title:_The Good, the Bad and the Beautiful (1970)_>, <Movie id:0136997[http] title:_Hirttämättömät (1971)_>]
            }
        )
    ]

    '''

    # Access the dictionary of connections
    connections = title.items()[0][1]

    # Find prequels or sequels
    ps = []
    if connection_type in connections:
        for connection in connections[connection_type]:
                connection_id = 'tt' + connection.movieID
                ps.append(connection_id)

    return ps

@st.cache_resource(show_spinner=False)
def get_ordered_connections(content, num_content_to_display, exclude_videogames=True):

    '''
    Return at least num_content_to_display connections as well as the index i of the last tconst searched
    '''
     
    # Create mini DataFrames to concat. Each one has the correct order of the connections.
    # These contain title and its connections.
    mini_dfs = []

    # Search through non-videogames. Connections could still be videogames though.
    if exclude_videogames:
        content_subset = content.loc[content['titleType'] != 'videoGame']
    else:
        content_subset = content.copy()

    # Avoid searching for connections of a title 
    # that has been previously searched.
    searched_tconsts = []

    # If tconst has a prequel, tconst 'follows' the prequel. When listing the prequel 
    # in the table, it will say that the prequel is 'Followed by' tconst (and viceversa).
    # e.g. Terminator 2 'follows' The Terminator. The Terminator is 'Followed by' the Terminator 2.
    # e.g. Breaking Bad is 'followed by' El Camino. El Camino 'Follows' Breaking Bad.
    connection_types = {'follows': 'Followed by', 'followed by': 'Follows'}

    # Go through each title in subset
    num_titles = 0

    for i, tconst in enumerate(content_subset['tconst']):
        
        if tconst in searched_tconsts:
            print('{}. NOT searching... {}'.format(i+1, content_subset.loc[content_subset['tconst'] == tconst, 'originalTitle'].values[0]))
        else:
            searched_tconsts.append(tconst)
            
            # Put tconst already in resulting dataframe
            mini_df = content_subset.loc[content_subset['tconst'] == tconst,:]
            print('{}. Searching... {} ({})'.format(i+1, content_subset.loc[content_subset['tconst'] == tconst, 'originalTitle'].values[0], tconst))

            # Iterate through sequels and prequels
            for ct in connection_types.keys():
                num_connections = get_num_connections(tconst, ct)   # Web-scrape number of connections

                # If connections are found
                if num_connections != 0:
                    connection_tconsts = find_title_connections(tconst, ct) # Get list of prequel(s) and sequel(s)
                    searched_tconsts += connection_tconsts  # Mark connections as seen
                    connection_rows = content[content['tconst'].isin(connection_tconsts)]   # Get connections data
                    
                    # Connection rows is derived from a merge between content and ratings.
                    # Number of connections could be 1, but connection rows could be 0 for a 
                    # title that has not yet been launched and/or received any ratings.
                    if len(connection_rows) != 0:

                        # Define type of connection
                        connection_rows['connection'] = '{} {} ({})'.format(
                            connection_types[ct], 
                            content_subset.loc[content_subset['tconst'] == tconst, 'originalTitle'].values[0],
                            tconst
                        )

                        # Connections of connections
                        # Not all connections are retrieved right now for the original title (only first 5 are shown,
                        # rest are collapsed with a 'see more' button). 
                        # Therefore we need to iterate through all connections to reach all of them.
                        print('{} --- {} --- Connections found: {} {} --- Total connections: {}'.format(tconst, ct, len(connection_rows), list(connection_rows['tconst']), num_connections))

                        # Keep searching connections until total amount is reached
                        while len(connection_rows) < num_connections:
                            # Oldest 5 connections (both ways) have been retrieved already since IMDB displays connections chronologically.
                            # Case 6+ prequels: Look for 5th and its successors --- Case 6+ sequels: Look for 5th and its successors
                            last_tconst = connection_rows.iloc[-1]['tconst']
                            print('Searching connections of {} ({})'.format(connection_rows.loc[connection_rows['tconst'] == last_tconst, 'primaryTitle'].values[0], last_tconst))
                            
                            missed_connection_tconsts = find_title_connections(last_tconst, 'followed by')
                            missed_connection_tconsts = [mct for mct in missed_connection_tconsts]
                            print('Missed connection tconsts:', missed_connection_tconsts)
                            searched_tconsts += missed_connection_tconsts
                            missed_connection_rows = content[content['tconst'].isin(missed_connection_tconsts)]

                            # It could be the case that a connection is found through the API, but it is not in the dataset.
                            # If that state is reached, do not continue search.
                            if len(missed_connection_rows) == 0:
                                break
                            
                            # Define type of connection
                            missed_connection_rows['connection'] = '{} {} ({})'.format(
                                connection_types[ct],
                                content_subset.loc[content_subset['tconst'] == tconst, 'originalTitle'].values[0],
                                tconst
                            )

                            connection_rows = pd.concat([connection_rows, missed_connection_rows])  # Update connections
                            print('Connection tconsts:', list(connection_rows['tconst']))
                            print('{} --- {} --- Connections found: {} --- Total connections: {}\n'.format(last_tconst, ct, len(connection_rows), num_connections))

                            '''
                            21. Searching... Star Wars: Episode V - The Empire Strikes Back (tt0080684)
                            tt0080684 --- follows --- Connections found: 1 ['tt0076759'] --- Total connections: 1
                            tt0080684 --- followed by --- Connections found: 5 ['tt0086190', 'tt2488496', 'tt0121766', 'tt0120915', 'tt0121765'] --- Total connections: 7
                            Searching connections of Star Wars: Episode II - Attack of the Clones (tt0121765)
                            Missed connection tconsts: ['tt2527336', 'tt2527338']
                            Connection tconsts: ['tt0086190', 'tt2488496', 'tt0121766', 'tt0120915', 'tt0121765', 'tt2527336', 'tt2527338']
                            tt0121765 --- followed by --- Connections found: 7 --- Total connections: 7
                            '''

                    # Avoid concating if connections and original have been watched already.
                    # Add only unwatched connections.
                    if connection_rows['userRating'].isnull().any():
                        mini_df = pd.concat([mini_df, connection_rows[connection_rows['userRating'].isnull()]])

            # If title and its connections have all been seen: skip it and don't add to the watchlist
            # Otherwise order by year
            if mini_df['userRating'].isnull().any():
                mini_df['index'] = mini_df.index
                mini_df.sort_values(['startYear', 'index'], inplace=True)
                mini_dfs.append(mini_df)

                num_titles += (mini_df['userRating'].isnull().sum() - len(mini_df[mini_df['titleType'] == 'videoGame']))
                print('Content unwatched:', num_titles)
                if num_titles >= num_content_to_display:
                    break

    # Put together all DataFrames of titles and their connections
    connections_ordered = pd.concat(mini_dfs)
    cols_of_interest = ['tconst', 'primaryTitle', 'connection', 'titleType', 'startYear', 'endYear', 'runtimeMinutes', 'numVotes', 'averageRating', 'score', 'userRating']
    connections_ordered = connections_ordered[cols_of_interest]
    connections_ordered.reset_index(drop=True, inplace=True)

    return connections_ordered, i