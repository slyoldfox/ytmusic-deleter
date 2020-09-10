from ytmusicapi import YTMusic
import click
import logging
import sys
import enlighten


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("ytmusic-deleter.log"),
        logging.StreamHandler(sys.stdout)
    ]
)


def setup():
    try:
        return YTMusic("headers_auth.json")
    except KeyError:
        sys.exit("Cookie invalid. Did you paste your cookie into headers_auth.json?")


youtube_auth = setup()
manager = enlighten.get_manager()


@click.group()
def cli():
    """Perform batch delete operations on your YouTube Music library.
    """


@cli.command()
@click.option("--add-to-library",
              "-a",
              is_flag=True,
              help="Add corresponding albums to your library before deleting them from uploads.")
def delete_uploads(add_to_library):
    # (albums_deleted, albums_total) = delete_uploaded_albums(add_to_library)
    # logging.info(f"Deleted {albums_deleted} out of {albums_total} uploaded albums.")
    # logging.info(f"\tRemaining {albums_total - albums_deleted} did not have a match in YouTube Music's online catalog.")

    (songs_deleted, songs_total) = delete_uploaded_songs()
    logging.info(f"Deleted {songs_deleted} out of {songs_total} uploaded songs that are not part of an album.")


def delete_uploaded_albums(add_to_library):
    logging.info("Retrieving all uploaded albums...")
    albums_deleted = 0
    uploaded_albums = youtube_auth.get_library_upload_albums(sys.maxsize)
    if not uploaded_albums:
        return (albums_deleted, 0)
    progress_bar = manager.counter(total=len(uploaded_albums), desc="Albums Processed", unit="albums")
    for album in uploaded_albums:
        try:
            artist = album["artists"][0]["name"] if len(album["artists"]) > 0 else "Unknown Artist"
            title = album["title"]
            logging.info(f"Processing album: {artist} - {title}")
            if add_to_library and not add_album_to_library(artist, title):
                progress_bar.update()
                continue
            response = youtube_auth.delete_upload_entity(album["browseId"])
            if response == "STATUS_SUCCEEDED":
                logging.info("\tDeleted album from uploads.")
                albums_deleted += 1
            else:
                logging.error("\tFailed to delete album from uploads")
        except (AttributeError, TypeError, KeyError) as e:
            logging.error(e)
        progress_bar.update()
    return (albums_deleted, len(uploaded_albums))


def delete_uploaded_songs():
    logging.info("Retrieving all uploaded songs that are not part of an album...")
    songs_deleted = 0
    uploaded_songs = None
    # Have to catch exception when there are no uploaded songs. Fixed in next release of ytmusicapi.
    try:
        uploaded_songs = youtube_auth.get_library_upload_songs(sys.maxsize)
    except KeyError:
        uploaded_songs = []
    if not uploaded_songs:
        return (songs_deleted, 0)

    # Filter for songs that don"t have an album, otherwise songs that
    # were skipped in the first batch would get deleted here
    uploaded_songs = [song for song in uploaded_songs if not song["album"]]

    progress_bar = manager.counter(total=len(uploaded_songs), desc="Songs Processed", unit="songs")

    for song in uploaded_songs:
        try:
            artist = song["artist"][0]["name"] if len(song["artist"]) > 0 else "Unknown Artist"
            title = song["title"]
            response = youtube_auth.delete_upload_entity(song["entityId"])
            if response == "STATUS_SUCCEEDED":
                logging.info(f"\tDeleted {artist} - {title}")
                songs_deleted += 1
            else:
                logging.error(f"\tFailed to delete {artist} - {title}")
        except (AttributeError, TypeError) as e:
            logging.error(e)
        progress_bar.update()

    return (songs_deleted, len(uploaded_songs))


def add_album_to_library(artist, title):
    logging.info("\tSearching for album in online catalog...")
    search_results = youtube_auth.search(f"{artist} {title}")
    for result in search_results:
        # Find the first album for which the artist and album title are substrings
        if result["resultType"] == "album" and artist.lower() in str(
                result["artist"]).lower() and title.lower() in str(result["title"]).lower():
            catalog_album = youtube_auth.get_album(result["browseId"])
            logging.info(f"\tFound matching album \"{catalog_album['title']}\" in YouTube Music. Adding to library...")
            for track in catalog_album["tracks"]:
                youtube_auth.rate_song(track["videoId"], "LIKE")
            logging.info("\tAdded album to library.")
            return True
    logging.warn("\tNo match for uploaded album found in online catalog. Will not delete.")
    return False


@cli.command()
def remove_library():
    albums_removed = 0
    while True:
        albums = youtube_auth.get_library_albums(100)
        if not albums:
            songs = youtube_auth.get_library_songs(100)
            if not songs:
                return albums_removed
            filtered_songs = list({v["album"]["id"]: v for v in songs}.values())
            for song in filtered_songs:
                album = youtube_auth.get_album(song["album"]["id"])
                artist = album["artist"][0]["name"] if len(album["artist"]) > 0 else "Unknown Artist"
                title = album["title"]
                logging.info(f"Removing {artist} - {title} from your library.")
                response = youtube_auth.rate_playlist(album["playlistId"], "INDIFFERENT")
        for album in albums:
            playlist_album = youtube_auth.get_album(album["browseId"])
            artist = playlist_album["artist"][0]["name"] if len(playlist_album["artist"]) > 0 else "Unknown Artist"
            title = playlist_album["title"]
            logging.info(f"Removing {artist} - {title} from your library.")
            response = youtube_auth.rate_playlist(playlist_album["playlistId"], "INDIFFERENT")
