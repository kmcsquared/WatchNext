# Script that fetches ratings directly from IMDB
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from datetime import date

url_imdb = 'https://www.imdb.com'

month_to_num = {
    'Jan': '01',
    'Feb': '02',
    'Mar': '03',
    'Apr': '04',
    'May': '05',
    'Jun': '06',
    'Jul': '07',
    'Aug': '08',
    'Sep': '09',
    'Oct': '10',
    'Nov': '11',
    'Dec': '12'
}

# Get to page with ratings (sorted by recently added)
def get_soup(id_user):

    url_user = '{}/user/{}/ratings?sort=date_added,desc&ratingFilter=0&mode=detail&ref_=undefined&lastPosition=0'.format(url_imdb, id_user)
    r = requests.get(url_user)
    soup = BeautifulSoup(r.content, 'html.parser')

    return soup

# Find number of ratings to know whether to move onto next page and keep searching
def get_num_pages(soup):

    list_pagination = soup.find('div', {'class': 'list-pagination'})
    
    '''
    EXAMPLE
    <div class="list-pagination">
                    <a class="flat-button prev-page disabled" href="#">
                    Previous
                </a>
                <span class="pagination-range">
                    1 - 100 of 241  
                </span>
                    <a class="flat-button lister-page-next next-page" href="/user/ur103598244/ratings?sort=date_added%2Cdesc&amp;mode=detail&amp;paginationKey=mfq5ijak6z7uymjwuuwsomnsegl34knnqsdztp6xeepepyyfxdfiwpol52uhtjimq3iwclnm7gq7uk2y4kjya3yimbzdwmhr7vbxy5e47iyfrvleknv4axfhhxudjs5nyx7ijakxrvcr564pajlxuqffl4f7yiuinvqyzrwxdnv2pcuv3nats7f7dya26nspsnfs62ipenhdqflymi&amp;lastPosition=100">
                    Next
                </a>
            </div>
    '''

    # Catch 403 Forbidden
    try:
        # Get number of films from: 1 - 100 of 241
        num_films = list_pagination.find('span', {'class': 'pagination-range'}).text.strip()    # Get text
    except AttributeError:
        return '403 Forbidden'
    
    num_films = num_films.split('of ')[-1]                                                  # '1 - 100 of 241' (get '241')
    num_films = int(num_films.replace(',', ''))                                             # e.g., convert '1,118' to 1118

    # Total amount of rating pages
    num_pages = 1 + (num_films // 100) # 100 shown per page
    
    return num_pages

# Switching to the next page
def get_next_page(current_num_page, soup):

    # Find next page
    list_pagination = soup.find('div', {'class': 'list-pagination'})
    next_page = list_pagination.find('a', {'class': 'flat-button lister-page-next next-page'})['href']

    # Scrape next page
    current_url = '{}{}'.format(url_imdb, next_page) 
    r = requests.get(current_url)
    soup = BeautifulSoup(r.content, 'html.parser')

    current_num_page += 1
    # print('Switching to ratings page {}: {}'.format(current_num_page, current_url))

    return current_num_page, soup

# Crawl and extract info
def extract_info(soup):

    '''
    Get user rating and year of rating for each title.
    Year will be used to check if new episodes have come out
    for a series which was rated the year before or earlier.
    '''

    # Dict linking ids and user ratings
    tconst_and_ratings = {}
    # Dict linking ids and rating date
    tconst_and_years_of_rating = {}

    # List containing all content in page
    content = soup.find_all('div', {'class':'lister-item-content'})
    
    for c in content:
        content_header = c.find('h3', {'class':'lister-item-header'}).a
        # <a href="/title/tt0328832/">The Animatrix</a>
        tconst = content_header['href'].split('/')[-2]
        # title = content_header.text

        user_rating = c.find('div', {'class':'ipl-rating-star ipl-rating-star--other-user small'}).find('span', {'class': 'ipl-rating-star__rating'}).text
        user_rating = int(user_rating)
        tconst_and_ratings[tconst] = user_rating

        # Episode dataset only has year of release N, so to find new episodes
        # we will need to check whether a new episode has been released in N+1.
        date_rating = c.find_all('p', {'class':'text-muted'})[1].text   # 'Rated on 17 Feb 2024'
        year_rating = int(date_rating.split(' ')[-1])  # 2024
        tconst_and_years_of_rating[tconst] = year_rating

    return tconst_and_ratings, tconst_and_years_of_rating

@st.cache_data(show_spinner=False)      # Run only once (when session begins)
def get_user_ratings(id_user='ur103598244'):

    soup = get_soup(id_user)
    num_pages = get_num_pages(soup)

    if num_pages != '403 Forbidden':   # Catch 403 Forbidden
        current_num_page = 1
        while current_num_page <= num_pages:
            print('Retrieving ratings from page {}/{}'.format(current_num_page, num_pages))
            # Extract info about (max) 100 titles per pages
            if current_num_page == 1:
                tconst_and_ratings, tconst_and_years_of_rating = extract_info(soup)
            else:
                next_tconst_and_ratings, next_tconst_and_years_of_rating = extract_info(soup)
                tconst_and_ratings.update(next_tconst_and_ratings)
                tconst_and_years_of_rating.update(next_tconst_and_years_of_rating)
            
            print('Content retrieved:', len(tconst_and_ratings), end='\n\n')

            # Move to the next page if not in last page yet
            if current_num_page == num_pages:
                break
            
            current_num_page, soup = get_next_page(current_num_page, soup)

        df_user_ratings = pd.DataFrame.from_dict(tconst_and_ratings, orient='index')
        df_user_ratings = df_user_ratings.reset_index().rename(columns={'index': 'tconst', 0: 'userRating'})

        df_dates_ratings = pd.DataFrame.from_dict(tconst_and_years_of_rating, orient='index')
        df_dates_ratings = df_dates_ratings.reset_index().rename(columns={'index': 'tconst', 0: 'dateRating'})

        df_user_ratings = pd.merge(df_user_ratings, df_dates_ratings, on='tconst')

    else:

        df_user_ratings = pd.read_csv('IMDB_Data/IMDB_Exported_Ratings.csv', index_col=0)
        df_user_ratings['dateRating'] = df_user_ratings['Date Rated'].apply(lambda x: int(x[:4]))    # YYYY-MM-DD -> YYYY
        df_user_ratings['tconst'] = df_user_ratings.index
        df_user_ratings.rename(columns={'Your Rating':'userRating'}, inplace=True)
        df_user_ratings = df_user_ratings[['tconst', 'userRating', 'dateRating']]
        df_user_ratings.to_csv('df_user_ratings.csv')

    return df_user_ratings
        


if __name__ == '__main__':
    
    tconst_and_ratings = get_user_ratings()
    print(tconst_and_ratings)