import fetching_connections as fc
import fetching_ratings as fr
import app_functions as af
import streamlit as st
import pandas as pd
import requests
from imdb import Cinemagoer
from PIL import Image
from io import BytesIO

# Page metadata
st.set_page_config(
    page_title='WatchNext',
    layout='wide'
)

st.title('WatchNext')
st.write(
    '''
    This website recommends films and series based on your preferences.
    If no preferences are selected, WatchNext's suggestions will be a mix of its 
    own ranking and unwatched connections of your rated content.
    '''
)

# # Entering user ID
# imdb_user_id = st.text_input('Enter your IMDB ID:', value='ur103598244', placeholder='ur...')

# # Check validity of ID
# try:
#     # Help out if user only enters numeric part of ID
#     if imdb_user_id.isnumeric():
#         imdb_user_id = 'ur' + imdb_user_id

#     with st.spinner('Fetching your IMDB ratings...'):
#         user_ratings = fr.get_user_ratings(imdb_user_id)
#         st.success('All ratings by *{}* have been found!'.format(imdb_user_id))

# except:
#     st.markdown(
#         '''
#         Enter a valid IMDB ID. To find it, go to your IMDB activity and look at the URL.
#         Your ID starts with ***ur*** and is followed by digits.
#         '''
#     )

with st.spinner('Fetching your IMDB ratings...'):
    user_ratings = fr.get_user_ratings()
    st.success('All your ratings by have been found!')

# Start load procedure
with st.spinner('Downloading latest films/series data:'):
    # Get necessary datasets for searching 
    titles, _, ratings = af.unzip_and_load_datasets()
    st.success('Latest film and series data has been loaded.')

with st.spinner('Preparing WatchNext rankings'):
    # Add user ratings to titles
    titles = titles.merge(user_ratings, how='left')     # Left to keep all unrated titles

    # Split titles by content type
    non_series = af.load_content_type('Non Series', titles)
    series = af.load_content_type('Series', titles)
    videogames = af.load_content_type('Videogames', titles)

    # Compute scores for each content type
    non_series = af.compute_scores(non_series, ratings)
    series = af.compute_scores(series, ratings)
    videogames = af.compute_scores(videogames, ratings)

# Merge all content types together
content = pd.concat([non_series, series, videogames])
content.sort_values('score', ascending=False, inplace=True)

num_content = st.number_input('Choose number of unwatched content to display', min_value=1, max_value=20, value=5)
with st.spinner('Fetching connections...'):
    connections_ordered = fc.get_ordered_connections(content, num_content)
    st.success('Connections will be displayed shortly.')

# Display content
cg = Cinemagoer()   # Get access to IMDB API for retrieving photos
n_cols = 5

# Idea:
# Loop through searched tconsts with unwatched connections
# Get connections
# Display them in order
searched_tconsts_with_unwatched_connections = connections_ordered.loc[connections_ordered['connection'].isnull(),:]

for searched_tconst in searched_tconsts_with_unwatched_connections['tconst']:
    tconst_row = searched_tconsts_with_unwatched_connections.loc[searched_tconsts_with_unwatched_connections['tconst'] == searched_tconst, :]
    # Get connections
    connections = connections_ordered.loc[connections_ordered['connection'].str.contains(searched_tconst, na=False),:]

    # Put connections and searched tconst together
    df = pd.concat([tconst_row, connections])
    df = df.sort_index()
    
    st.header('Based on: {}'.format(tconst_row['primaryTitle'].values[0]))
    for idx, tconst in enumerate(df['tconst']):
        # Fetch image if not retrieved already
        if tconst not in st.session_state:
            content = cg.get_movie(tconst[2:])

            # TO-DO: Get image link from the web scraping
            # Read and resize image: https://stackoverflow.com/questions/7391945/how-do-i-read-image-data-from-a-url-in-python
            img_data = requests.get(content['full-size cover url']).content
            content_image = Image.open(BytesIO(img_data)).resize((1200,1800))
            
            # Save variables obtained through requests in cache
            st.session_state['content_{}'.format(tconst)] = content
            st.session_state['image_{}'.format(tconst)] = content_image
            
            tconst_info = connections_ordered.loc[connections_ordered['tconst'] == tconst].values[0]
            primary_title = tconst_info[1]
            title_type = tconst_info[3]
            start_year = tconst_info[4]
            end_year = tconst_info[5]
            if end_year == '\\N':
                end_year = ''
            score = tconst_info[-2]
            content_caption = '{}. {} ({:.2f}) --- {} ({}{})'.format(
                idx+1, 
                primary_title,
                score,
                title_type,
                start_year,
                '-{}'.format(end_year) if 'Series' in title_type else ''
            )

        # Add a new row when end of row is reached
        if idx % n_cols == 0:
            cols = st.columns(n_cols)

        cols[idx % n_cols].image(st.session_state['image_{}'.format(tconst)], caption=content_caption)

    st.divider()

st.cache_data.clear()