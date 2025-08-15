import smtplib
import requests
from email.message import EmailMessage
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from premailer import transform

load_dotenv()

app = Flask(__name__)


TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

def get_rotten_tomatoes_scores(imdb_id):
    """Fetches movie ratings from OMDb and prints debug info."""
    if not imdb_id or not OMDB_API_KEY:
        print("[RT DEBUG] Skipped: Missing IMDb ID or OMDb API Key.")
        return None
    
    try:
        omdb_url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
        print(f"[RT DEBUG] Fetching scores for IMDb ID: {imdb_id}")
        print(f"[RT DEBUG] OMDb URL: {omdb_url.split('&apikey=')[0]}&apikey=...")
        
        response = requests.get(omdb_url)
        response.raise_for_status()
        data = response.json()
        
        print(f"[RT DEBUG] OMDb Response: {data}")

        if data.get("Response") == "True":
            for rating in data.get("Ratings", []):
                if rating["Source"] == "Rotten Tomatoes":
                    return rating["Value"]
    except requests.RequestException as e:
        print(f"[RT DEBUG] OMDb request failed: {e}")
    except Exception as e:
        print(f"[RT DEBUG] An error occurred parsing OMDb data: {e}")
    return None

def generate_newsletter_html(data):
    """Generates the final newsletter HTML using a table-based layout for email client compatibility."""
    intro_html = f"<p style='font-size: 16px; line-height: 1.6;'>{data.get('introText', '').replace('\n', '<br>')}</p>"
    
    new_items_html = ""
    if data.get("newItems"):
        new_items_html = "<h2 style='color: #343a40; border-bottom: 2px solid #dee2e6; padding-bottom: 10px; margin-top: 30px;'>New This Week</h2>"
        for item in data["newItems"]:
            new_items_html += render_item_card(item)

    featured_items_html = ""
    if data.get("featuredItems"):
        featured_intro = data.get('featuredIntroText', 'Also on the server, check out these library picks!')
        processed_featured_intro = featured_intro.replace('\n', '<br>')
        featured_items_html = f"<h2 style='color: #343a40; border-bottom: 2px solid #dee2e6; padding-bottom: 10px; margin-top: 30px;'>Featured Library Picks</h2><p>{processed_featured_intro}</p>"
        for item in data["featuredItems"]:
            featured_items_html += render_item_card(item)
    
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset='UTF-8'></head>
    <body style='font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px; max-width: 800px; margin: auto;'>
        <h1 style='color: #343a40;'>🎬 New on Dante’s Plex</h1>
        {intro_html}
        {new_items_html}
        {featured_items_html}
    </body>
    </html>
    """
    return full_html

def render_item_card(item):
    """Helper function to render a single movie/show card HTML using a table layout."""
    rt_block = ""
    if item.get("rt_critic_score"):
        rt_block = f"""
            <td width="15"></td>
            <td valign="top" align="left" style="text-align: left;">
                <div style="font-size: 16px; font-weight: bold; color: #333;">🍅 {item['rt_critic_score']}</div>
                <div style="font-size: 12px; color: #555;">Tomatometer</div>
            </td>
        """
    
    return f"""
    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background: white; border-radius: 10px; margin-bottom: 20px;">
        <tr>
            <td style="padding: 15px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr>
                        <td width="150" valign="top">
                            <img src="{item['poster_url']}" alt="{item['title']} poster" width="150" style="width: 150px; border-radius: 8px; display: block;">
                        </td>
                        <td width="20"></td>
                        <td valign="top">
                            <div style="font-size: 20px; font-weight: bold; margin-bottom: 5px;">{item['title']} ({item['year']})</div>
                            <div style="font-size: 14px; color: #777; margin-bottom: 8px;">{item.get('type', 'Movie')}</div>
                            
                            <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 8px;">
                                <tr>
                                    <td valign="top" align="left" style="text-align: left;">
                                        <div style="font-size: 16px; font-weight: bold; color: #333;">⭐ {item['rating']}/10</div>
                                        <div style="font-size: 12px; color: #555;">TMDB ({item['votes']:,} votes)</div>
                                    </td>
                                    {rt_block}
                                </tr>
                            </table>
                            <div style="font-size: 14px; color: #555; margin-bottom: 8px;">{item['genres']}</div>
                            <div style="font-style: italic; margin-bottom: 12px; border-left: 3px solid #eee; padding-left: 10px;">"{item.get('blurb', 'No blurb provided.')}"</div>
                            <div style="font-size: 14px; color: #333;">{item['overview']}</div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    """

# Keep the /search endpoint the same as before
@app.route("/search")
def search_media():
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    try:
        movie_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}"
        tv_url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}"
        movie_results = requests.get(movie_url).json().get("results", [])
        tv_results = requests.get(tv_url).json().get("results", [])
        items = []
        for res in movie_results:
            if res.get("poster_path") and res.get("release_date"):
                items.append({"id": res["id"], "type": "movie", "title": res["title"], "year": res["release_date"][:4], "poster_url": f"https://image.tmdb.org/t/p/w200{res['poster_path']}"})
        for res in tv_results:
            if res.get("poster_path") and res.get("first_air_date"):
                items.append({"id": res["id"], "type": "tv", "title": res["name"], "year": res["first_air_date"][:4], "poster_url": f"https://image.tmdb.org/t/p/w200{res['poster_path']}"})
        items.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

def enrich_item(item):
    """Fetches full details for a single item (movie or TV) from APIs."""
    item_type = item.get("type", "movie")
    if item_type == "movie":
        details_url = f"https://api.themoviedb.org/3/movie/{item['id']}?api_key={TMDB_API_KEY}"
        details = requests.get(details_url).json()
        rt_score = get_rotten_tomatoes_scores(details.get("imdb_id"))
        return {
            "type": "Movie", "title": details.get("title"), "year": details.get("release_date", "")[:4],
            "rating": round(details.get("vote_average", 0), 1), "votes": details.get("vote_count", 0),
            "genres": ", ".join(g["name"] for g in details.get("genres", [])),
            "poster_url": f"https://image.tmdb.org/t/p/w500{details.get('poster_path', '')}",
            "overview": details.get("overview", ""), "blurb": item.get("blurb", ""),
            "rt_critic_score": rt_score
        }
    elif item_type == "tv":
        details_url = f"https://api.themoviedb.org/3/tv/{item['id']}?api_key={TMDB_API_KEY}"
        details = requests.get(details_url).json()
        return {
            "type": "TV Show", "title": details.get("name"), "year": details.get("first_air_date", "")[:4],
            "rating": round(details.get("vote_average", 0), 1), "votes": details.get("vote_count", 0),
            "genres": ", ".join(g["name"] for g in details.get("genres", [])),
            "poster_url": f"https://image.tmdb.org/t/p/w500{details.get('poster_path', '')}",
            "overview": details.get("overview", ""), "blurb": item.get("blurb", "")
        }
    return None

@app.route("/generate", methods=["POST"])
def generate():
    """API endpoint to generate the newsletter, now handling complex data."""
    data = request.json
    try:
        enriched_new = [enrich_item(item) for item in data.get("newItems", [])]
        enriched_featured = [enrich_item(item) for item in data.get("featuredItems", [])]
        
        enriched_new = [i for i in enriched_new if i]
        enriched_featured = [i for i in enriched_featured if i]

        final_data = {
            "introText": data.get("introText"),
            "newItems": enriched_new,
            "featuredIntroText": data.get("featuredIntroText"),
            "featuredItems": enriched_featured,
        }
        
        original_html = generate_newsletter_html(final_data)
        email_ready_html = transform(original_html)
        return jsonify({"html": email_ready_html})

    except Exception as e:
        print(f"[ERROR] Failed to generate HTML: {e}")
        return jsonify({"error": f"Failed to generate HTML: {e}"}), 500

@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.json
    recipients = data.get("recipients")
    subject = data.get("subject")
    html_content = data.get("html")

    if not all([recipients, subject, html_content]):
        return jsonify({"error": "Missing recipients, subject, or HTML content"}), 400


    sender_email = os.getenv("GMAIL_USER")
    sender_password = os.getenv("GMAIL_PASSWORD")

    if not sender_email or not sender_password:
         return jsonify({"error": "Email credentials are not configured on the server."}), 500

    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipients


        msg.set_content("This is a fallback for email clients that do not support HTML.")
        msg.add_alternative(html_content, subtype='html')


        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        
        return jsonify({"message": "Email sent successfully!"})

    except Exception as e:
        print(f"[ERROR] Could not send email: {e}")
        return jsonify({"error": f"Failed to send email: {e}"}), 500

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)