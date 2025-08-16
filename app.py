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
PLEX_OWNER_NAME = os.getenv("PLEX_OWNER_NAME", "Plex")

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
    intro_text = data.get('introText', '').replace('\n', '<br>')
    intro_html = f"<p style='font-size: 16px; line-height: 1.6;'>{intro_text}</p>"
    
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
        <h1 style='color: #343a40;'>🎬 New on {PLEX_OWNER_NAME}'s Plex</h1>
        {intro_html}
        {new_items_html}
        {featured_items_html}
    </body>
    </html>
    """
    return full_html

def generate_magazine_newsletter_html(data):
    """Generates a magazine-style newsletter HTML with featured items prominently displayed."""
    intro_text = data.get('introText', '').replace('\n', '<br>')
    intro_html = f"<p style='font-size: 16px; line-height: 1.6; margin-bottom: 30px;'>{intro_text}</p>"
    
    # Magazine header
    header_html = f"""
    <div style='text-align: center; margin-bottom: 40px; border-bottom: 3px solid #e74c3c; padding-bottom: 20px;'>
        <h1 style='font-size: 36px; font-weight: bold; color: #2c3e50; margin: 0; letter-spacing: 2px;'>MONTHLY NEWSLETTER</h1>
        <p style='font-size: 14px; color: #7f8c8d; margin: 5px 0 0 0;'>{PLEX_OWNER_NAME}'s Plex Server</p>
    </div>
    """
    
    # New This Week section
    new_section_html = ""
    if data.get("featuredNewItem") or data.get("newItems"):
        # Exclude the featured item from additional items
        new_additional_items = data.get("newItems", [])[1:] if data.get("newItems") else []
        new_section_html = render_magazine_section(
            title="NEW THIS WEEK",
            featured_item=data.get("featuredNewItem"),
            additional_items=new_additional_items,
            longform_content=data.get("newItemsLongform", "")
        )
    
    # Featured Library Picks section
    featured_section_html = ""
    if data.get("featuredLibraryItem") or data.get("featuredItems"):
        # Exclude the featured item from additional items
        featured_additional_items = data.get("featuredItems", [])[1:] if data.get("featuredItems") else []
        featured_section_html = render_magazine_section(
            title="PLEX PICKS - THIS WEEK'S FEATURE",
            featured_item=data.get("featuredLibraryItem"),
            additional_items=featured_additional_items,
            longform_content=data.get("libraryPicksLongform", "")
        )
    
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset='UTF-8'></head>
    <body style='font-family: Georgia, serif; background-color: #f8f9fa; padding: 20px; max-width: 900px; margin: auto;'>
        {header_html}
        {intro_html}
        {new_section_html}
        {featured_section_html}
    </body>
    </html>
    """
    return full_html

def render_magazine_section(title, featured_item, additional_items, longform_content):
    """Renders a magazine-style section with featured item on left and small cards on right."""
    print(f"[DEBUG] render_magazine_section - title: {title}, longform_content: '{longform_content}'")
    section_html = f"""
    <div style='margin-bottom: 50px;'>
        <h2 style='font-size: 24px; font-weight: bold; color: #2c3e50; text-align: center; margin-bottom: 30px; text-transform: uppercase; letter-spacing: 1px;'>{title}</h2>
        <table cellpadding='0' cellspacing='0' border='0' width='100%'>
            <tr>
                <td width='60%' valign='top' style='padding-right: 20px;'>
    """
    
    # Featured item on the left
    if featured_item:
        section_html += render_featured_item(featured_item, longform_content)
    else:
        section_html += "<div style='background: #ecf0f1; padding: 40px; text-align: center; border-radius: 10px; color: #7f8c8d;'>No featured item selected</div>"
    
    section_html += """
                </td>
                <td width='40%' valign='top'>
    """
    
    # Small cards on the right
    if additional_items:
        section_html += "<div style='background: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);'>"
        section_html += "<h3 style='font-size: 16px; color: #2c3e50; margin: 0 0 15px 0; text-align: center;'>Also This Week</h3>"
        for item in additional_items:
            section_html += render_small_card(item)
        section_html += "</div>"
    else:
        section_html += "<div style='background: #ecf0f1; padding: 20px; text-align: center; border-radius: 10px; color: #7f8c8d;'>No additional items</div>"
    
    section_html += """
                </td>
            </tr>
        </table>
    </div>
    """
    
    return section_html

def render_featured_item(item, longform_content=""):
    """Renders a large featured item for the magazine layout."""
    print(f"[DEBUG] render_featured_item - item: {item['title'] if item else 'None'}, longform_content: '{longform_content}'")
    rt_block = ""
    if item.get("rt_critic_score"):
        rt_block = f"<div style='color: #e74c3c;'>🍅 {item['rt_critic_score']}</div>"
    
    # Handle custom blurb (user-entered blurb) with italic grey styling
    custom_blurb_html = ""
    if item.get('blurb'):
        custom_blurb_html = f"<div style='font-size: 15px; color: #7f8c8d; line-height: 1.6; font-style: italic; margin-top: 15px;'>\"{item['blurb']}\"</div>"
    
    # Use longform content as the Editor's Note with black text
    blurb_html = ""
    if longform_content:
        processed_longform = longform_content.replace('\n', '<br>')
        blurb_html = f"<div style='margin-top: 20px; clear: both;'><h4 style='font-size: 16px; font-weight: bold; color: #2c3e50; margin: 0 0 10px 0; border-bottom: 1px solid #ecf0f1; padding-bottom: 5px;'>Editor's Note</h4><div style='font-size: 15px; color: #000000; line-height: 1.6;'>{processed_longform}</div></div>"
        print(f"[DEBUG] blurb_html generated: {blurb_html[:100]}...")
    
    return f"""
    <div style='background: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px;'>
        <div style='overflow: hidden;'>
            <img src="{item['poster_url']}" alt="{item['title']} poster" style="width: 200px; height: 300px; object-fit: cover; float: left; margin: 0 25px 15px 0; border-radius: 8px;">
            
            <h3 style='font-size: 24px; font-weight: bold; margin: 0 0 8px 0; color: #2c3e50;'>{item['title']}</h3>
            <p style='font-size: 16px; color: #7f8c8d; margin: 0 0 15px 0;'>{item['year']} • {item.get('type', 'Movie')}</p>
            
            <div style='margin-bottom: 15px;'>
                <div style='margin-bottom: 5px;'>
                    <span style='font-size: 18px; font-weight: bold; color: #f39c12;'>⭐ {item['rating']}/10</span>
                    <span style='font-size: 14px; color: #95a5a6; margin-left: 10px;'>({item['votes']:,} votes)</span>
                </div>
                {rt_block if item.get('rt_critic_score') else ''}
            </div>
            
            <p style='font-size: 14px; color: #7f8c8d; margin: 0 0 15px 0; font-weight: 500;'>{item['genres']}</p>
            
            <div style='font-size: 15px; color: #2c3e50; line-height: 1.6;'>{item['overview']}</div>
            
            {custom_blurb_html}
            
            {blurb_html}
        </div>
    </div>
    """

def render_small_card(item):
    """Renders a small card for additional items in the magazine layout."""
    rt_block = ""
    if item.get("rt_critic_score"):
        rt_block = f" • 🍅 {item['rt_critic_score']}"
    
    custom_blurb = ""
    if item.get('blurb'):
        custom_blurb = f"<p style='font-size: 11px; color: #2c3e50; line-height: 1.3; margin: 4px 0 0 0; font-style: italic;'>\"{item['blurb']}\"</p>"
    
    return f"""
    <div style='display: flex; margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #ecf0f1;'>
        <div style='flex-shrink: 0; margin-right: 12px;'>
            <img src="{item['poster_url']}" alt="{item['title']} poster" width="60" style="width: 60px; height: 90px; object-fit: cover; border-radius: 5px; display: block;">
        </div>
        <div style='flex: 1; min-width: 0;'>
            <h4 style='font-size: 14px; font-weight: bold; margin: 0 0 4px 0; color: #2c3e50; line-height: 1.3;'>{item['title']}</h4>
            <p style='font-size: 12px; color: #7f8c8d; margin: 0 0 6px 0;'>{item['year']} • {item.get('type', 'Movie')}</p>
            <div style='font-size: 12px; color: #f39c12; margin-bottom: 4px;'>⭐ {item['rating']}/10{rt_block}</div>
            <p style='font-size: 11px; color: #95a5a6; line-height: 1.3; margin: 0;'>{item['genres']}</p>
            {custom_blurb}
        </div>
    </div>
    """

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
    """API endpoint to generate the newsletter, now handling both classic and magazine layouts."""
    data = request.json
    try:
        print(f"[DEBUG] Received data keys: {list(data.keys())}")
        
        # Check if this is a magazine-style request (from alt interface)
        is_magazine_style = (
            data.get("featuredNewItem") is not None or 
            data.get("featuredLibraryItem") is not None or
            data.get("newItemsLongform") is not None or
            data.get("libraryPicksLongform") is not None
        )
        
        print(f"[DEBUG] Magazine style detected: {is_magazine_style}")
        
        if is_magazine_style:
            # Handle magazine-style layout
            enriched_new = [enrich_item(item) for item in data.get("newItems", [])]
            enriched_featured = [enrich_item(item) for item in data.get("featuredItems", [])]
            
            # Enrich featured items
            enriched_featured_new = None
            if data.get("featuredNewItem"):
                enriched_featured_new = enrich_item(data["featuredNewItem"])
                print(f"[DEBUG] Enriched featured new item: {enriched_featured_new['title'] if enriched_featured_new else 'None'}")
            
            enriched_featured_library = None
            if data.get("featuredLibraryItem"):
                enriched_featured_library = enrich_item(data["featuredLibraryItem"])
                print(f"[DEBUG] Enriched featured library item: {enriched_featured_library['title'] if enriched_featured_library else 'None'}")
            
            enriched_new = [i for i in enriched_new if i]
            enriched_featured = [i for i in enriched_featured if i]
            
            final_data = {
                "introText": data.get("introText"),
                "featuredNewItem": enriched_featured_new,
                "newItems": enriched_new,
                "newItemsLongform": data.get("newItemsLongform", ""),
                "featuredLibraryItem": enriched_featured_library,
                "featuredItems": enriched_featured,
                "libraryPicksLongform": data.get("libraryPicksLongform", "")
            }
            
            print(f"[DEBUG] newItemsLongform: '{data.get('newItemsLongform', '')}'")
            print(f"[DEBUG] libraryPicksLongform: '{data.get('libraryPicksLongform', '')}'")
            
            print(f"[DEBUG] Generating magazine-style newsletter")
            original_html = generate_magazine_newsletter_html(final_data)
        else:
            # Handle classic layout
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
            
            print(f"[DEBUG] Generating classic newsletter")
            original_html = generate_newsletter_html(final_data)
        
        email_ready_html = transform(original_html)
        print(f"[DEBUG] Newsletter generated successfully")
        return jsonify({"html": email_ready_html})

    except Exception as e:
        print(f"[ERROR] Failed to generate HTML: {e}")
        import traceback
        traceback.print_exc()
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

@app.route("/alt")
def index_alt():
    return render_template("index-alt.html")

if __name__ == "__main__":
    app.run(debug=True)