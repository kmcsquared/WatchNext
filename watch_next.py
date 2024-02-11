import streamlit as st
import numpy as np
import pandas as pd
import app_functions as af
from fetching_ratings import get_user_ratings
from datetime import datetime

st.title('WatchNext')

if 'loaded_data' not in st.session_state:

    with st.spinner('Downloading IMDB datasets...'):
        # Load datasets
        datasets = af.unzip_and_load_datasets()
        df_imdb_titles = datasets[0]
        df_imdb_ratings = datasets[1]
        df_imdb_episodes = datasets[2]

    with st.spinner('Merging ratings information...'):
        df_imdb_titles = af.merge_ratings(df_imdb_titles, df_imdb_ratings)
        
        st.write('DF_IMDB_TITLES')
        st.dataframe(df_imdb_titles.head())
        df_episodes = af.merge_episode_info(df_imdb_episodes, df_imdb_titles)

    with st.spinner('Normalising scores...'):
        df_episodes = af.normalise_content(df_episodes)
        st.write('DF_IMDB_EPISODES')
        st.dataframe(df_episodes.head())

        df_films = df_imdb_titles.loc[~(df_imdb_titles['titleType'].isin(['tvSeries', 'tvMiniSeries', 'tvEpisode']))]
        df_films = af.normalise_content(df_films)
        df_series = df_imdb_titles.loc[df_imdb_titles['titleType'].isin(['tvSeries', 'tvMiniSeries', 'tvEpisode'])]
        df_series = af.normalise_content(df_series)
        df_series.rename(columns={'score': 'seriesScore'}, inplace=True)

    with st.spinner('Calculating series metrics'):
        df_episode_metric = af.calculate_episode_metric(df_episodes)
        df_runtime_metric = af.calculate_runtime_metric(df_episodes)
        df_combined_metric = af.calculate_combined_metric(
            df_series,
            df_episode_metric,
            df_runtime_metric
        )

    with st.spinner('Loading user ratings...'):
        # Load user ratings
        seen_tconst = get_user_ratings()['tconst']

    keys = ['films', 'series', 'user_ratings']
    values = [df_films, df_combined_metric, seen_tconst]

    for k, v in zip(keys, values):
        if k not in st.session_state:
            st.session_state[k] = v
    
    st.session_state['loaded_data'] = True

df_films = st.session_state['films'].copy()
df_series = st.session_state['series'].copy()
watched_tconst = st.session_state['user_ratings'].copy()

# Films
st.header('FILMS')

show_watched_films = st.toggle(
    label='Show watched films',
    value=False
)

if not show_watched_films:
    df_films = df_films.loc[~(df_films['tconst'].isin(watched_tconst))]

df_films.index = np.arange(1, 1+len(df_films))


num_films = st.slider(
    label='Select number of films to display',
    min_value=1,
    max_value=50,
    value=10
)

st.dataframe(df_films[:num_films])

# Series
st.header('SERIES')

show_watched_series = st.toggle(
    label='Show watched series',
    value=False
)

show_unfinished_series = st.toggle(
    label='Show ongoing series',
    value=False
)

if not show_watched_series:
    df_series = df_series.loc[~(df_series['tconst'].isin(watched_tconst))]

if not show_unfinished_series:
    df_series = df_series.loc[df_series['endYear'] != '\\N']
    df_series = df_series.loc[df_series['endYear'].astype(int) <= datetime.now().year]

df_series.index = np.arange(1, 1+len(df_series))

num_series = st.slider(
    label='Select number of series to display',
    min_value=1,
    max_value=50,
    value=10
)

st.dataframe(df_series[:num_series])