from bs4 import BeautifulSoup
from imdb import Cinemagoer
import streamlit as st
import pandas as pd
import requests

import app_functions as af


cg = Cinemagoer()


# API does not return the total amount of connections due to a button
# that needs to be clicked to 'see more' connections
@st.cache_resource(show_spinner=False)
def get_num_connections(tconst, connection_type):

    '''
    This is done through web-scraping instead of using the Cinemagoer connections
    since Cinemagoer does not give the real number. Because IMDB has an expandable
    button to show beyond 5 prequels/sequels, Cinemagoer only shows 5 connections
    as a maximum. 
    '''

    url_user = 'https://www.imdb.com/title/{}/movieconnections/'.format(tconst)
    user_agent = {'User-agent': 'Mozilla/5.0'}
    r = requests.get(url_user, headers=user_agent)
    soup = BeautifulSoup(r.content, 'html.parser')

    if connection_type == 'followed by':
        connection_type = 'followed_by' 

    connection = soup.find('option', {'value':'#'+connection_type})     # # e.g. <option value="#follows">Follows (1)</option>
    if connection is None:
        return 0
    
    txt = connection.text       # Follows (1)
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

@st.cache_data(show_spinner=False)
def get_ordered_connections(content_ranked, all_content, max_num_titles, seen_tconst):

    '''
    Return at least max_num_titles unwatched titles.

    content_ranked: Post-processed data with normalised scores
    all_content: Unprocessed data
                    - Because content_ranked uses series and films with more than 5000
                    votes for score normalisation, all_content is needed to retrieve 
                    those connections with less than 5000 votes which would be lost.
    '''

    # Create mini DataFrames for each title and their connections. Each one has the correct order of the connections.
    # Then concat all of them together to get a DataFrame of connections.
    mini_dfs = []

    # Avoid searching for connections of a title 
    # that has been previously searched.
    searched_tconsts = set()

    # If tconst has a prequel, tconst 'follows' the prequel. When listing the prequel 
    # in the table, it will say that the prequel is 'Followed by' tconst (and viceversa).
    # e.g. Terminator 2 'follows' The Terminator. The Terminator is 'Followed by' the Terminator 2.
    # e.g. Breaking Bad is 'followed by' El Camino. El Camino 'Follows' Breaking Bad.
    connection_types = {
        'follows': 'Followed by', 
        'followed by': 'Follows'
    }

    # Go through each title in subset
    num_titles_with_connections = 0

    # Print out to the screen title being searched
    log = st.empty()

    for i, tconst in enumerate(content_ranked['tconst']):

        tconst_title = all_content.loc[all_content['tconst'] == tconst, 'primaryTitle'].values[0]
        
        if tconst in searched_tconsts:
            print('{}. NOT searching... {} ({})'.format(i+1, tconst_title, tconst), end='\n\n')
            with log.container():
                st.write('{}. NOT searching... {} ({})'.format(i+1, tconst_title, tconst))
        else:
            print('{}. Searching... {} ({})'.format(i+1, tconst_title, tconst), end='\n\n')
            with log.container():
                st.write('{}. Searching... {} ({})'.format(i+1, tconst_title, tconst))

            searched_tconsts.add(tconst)

            # Put tconst already in resulting dataframe
            mini_df = all_content.loc[all_content['tconst'] == tconst].copy()
            
            # Iterate through sequels and prequels
            for conn_type in connection_types.keys():
                search_round = 1
                num_connections = get_num_connections(tconst, conn_type)   # Web-scrape number of connections
                
                # Connection tconst are returned in the same order as on IMDB
                connection_tconsts = find_title_connections(tconst, conn_type)
                
                print(
                    '{} - Search round {} ({}/{}): {}'.format(
                        conn_type,
                        search_round,
                        len(connection_tconsts),
                        num_connections, 
                        connection_tconsts
                    ), 
                    end='\n\n' if conn_type == 'followed by' else '\n'
                )

                if len(connection_tconsts) != 0:
                    for conn_tconst in connection_tconsts:
                        searched_tconsts.add(conn_tconst)   # Mark connections as seen

                    connection_rows = all_content.loc[all_content['tconst'].isin(connection_tconsts)].copy()

                    # Keep order of the list connection_tconsts in DataFrame
                    # https://stackoverflow.com/questions/23414161/pandas-isin-with-output-keeping-order-of-input-list
                    connection_rows['tconst_order'] = pd.Categorical(
                        values=connection_rows['tconst'],
                        categories=connection_tconsts,
                        ordered=True
                    )

                    connection_rows.sort_values('tconst_order', inplace=True)


                    # Connection rows is derived from a merge between all_content and ratings.
                    # Number of connections could be 1, but connection rows could be 0 for a 
                    # title that has not yet been launched and/or received any ratings.
                    if len(connection_rows) != 0:

                        # Define type of connection (e.g. Follows The Dark Knight (tconst)))
                        connection_rows['connection'] = '{} {} ({})'.format(
                            connection_types[conn_type],
                            tconst_title,
                            tconst
                        )

                        # Not all connections of tconst are retrieved through Cinemagoer due to an 
                        # expandable button. Therefore we need to iterate through the connections' 
                        # connections until the number of connections of tconst is reached.
                        while len(connection_rows) < num_connections:
                            
                            # First 5 prequels/sequels are retrieved initially
                            # In the case of 6+ prequels/sequels, get 5th and find its successors
                            last_tconst = connection_rows.iloc[-1]['tconst']
                            last_tconst_title = connection_rows.loc[connection_rows['tconst'] == last_tconst, 'primaryTitle'].values[0]
                            print('Searching connections of {} ({})'.format(last_tconst_title, last_tconst))

                            # Connections hidden in the expandable button which follow the last one retrieved
                            missed_connection_tconsts = find_title_connections(last_tconst, 'followed by')
                            # missed_connection_tconsts = [mct for mct in missed_connection_tconsts if mct not in connection_rows['tconst']]
                            print('Missed connection tconsts:', missed_connection_tconsts)
                            for mct in missed_connection_tconsts:
                                searched_tconsts.add(mct)

                            missed_connection_rows = all_content.loc[all_content['tconst'].isin(missed_connection_tconsts)].copy()

                            # It could be the case that a connection is found through the API, but it is not in the dataset due to
                            # non-existent ratings. If that state is reached, do not continue search.
                            if len(missed_connection_rows) == 0:
                                print('Lost connections:', missed_connection_tconsts, end='\n\n')
                                break

                            # Define type of connection (e.g. Follows The Dark Knight (tconst)))
                            missed_connection_rows['connection'] = '{} {} ({})'.format(
                                connection_types[conn_type],
                                tconst_title,
                                tconst
                            )

                            connection_rows = pd.concat([connection_rows, missed_connection_rows])  # Update connections
                            search_round += 1
                            print('{} - Search round {}: {}\n\n'.format(conn_type, search_round, list(connection_rows['tconst'])))
                            # print('Connection tconsts:', list(connection_rows['tconst']))
                            print('{} --- {} --- Connections found: {}/{}\n'.format(
                                last_tconst, 
                                conn_type, 
                                len(connection_rows), 
                                num_connections)
                            )

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
                    is_unwatched_connection = ~(connection_rows['tconst'].isin(seen_tconst))
                    if is_unwatched_connection.sum() > 0:
                        unwatched_connections = connection_rows.loc[is_unwatched_connection]
                        mini_df = pd.concat([mini_df, unwatched_connections])

            # If title and its connections have all been seen: skip it and don't add to the watchlist
            # Otherwise order by year
            is_unwatched_connection = ~(mini_df['tconst'].isin(seen_tconst))
            if is_unwatched_connection.sum() > 0:
                # mini_df['index'] = mini_df.index
                # mini_df = mini_df.sort_values(['startYear', 'index'])
                mini_dfs.append(mini_df)
                num_titles_with_connections += 1
                print('Number of titles unseen:', num_titles_with_connections, end='\n\n')
                if num_titles_with_connections >= max_num_titles:
                    break

    connections_ordered = pd.concat(mini_dfs)
    # print(connections_ordered)
    cols_of_interest = ['tconst', 'primaryTitle', 'connection', 'titleType', 'startYear', 'endYear', 'runtimeMinutes', 'numVotes', 'averageRating']
    connections_ordered = connections_ordered[cols_of_interest]
    connections_ordered.reset_index(drop=True, inplace=True)

    return connections_ordered