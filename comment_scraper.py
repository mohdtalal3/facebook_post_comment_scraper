import requests
import json
import time

GRAPHQL = "https://www.facebook.com/api/graphql/"


session = requests.Session()
session.headers.update({
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded"
})

# ===== PAYLOADS =====

def comments_payload(feedback_id, cursor=None):
    return {
        "av": "0",
        "__user": "0",
        "__a": "1",
        "doc_id": "25550760954572974",
        "variables": json.dumps({
            "commentsAfterCount": -1,
            "commentsAfterCursor": cursor,
            "feedLocation": "POST_PERMALINK_DIALOG",
            "focusCommentID": None,
            "scale": 2,
            "useDefaultActor": False,
            "id": feedback_id
        })
    }


def replies_payload(comment_feedback_id, expansion_token):
    return {
        "av": "0",
        "__user": "0",
        "__a": "1",
        "doc_id": "26570577339199586",
        "variables": json.dumps({
            "clientKey": None,
            "expansionToken": expansion_token,
            "feedLocation": "POST_PERMALINK_DIALOG",
            "focusCommentID": None,
            "scale": 2,
            "useDefaultActor": False,
            "id": comment_feedback_id
        })
    }

# ===== FETCH COMMENTS =====
import json

def fb_json(response_text):
    """
    Facebook GraphQL sometimes returns:
    for (;;);
    {json}
    {json}

    This extracts the first valid JSON object safely.
    """
    text = response_text.strip()

    # Remove for (;;);
    if text.startswith("for (;;);"):
        text = text[len("for (;;);"):]

    # Keep only first JSON object
    first = text.split("\n")[0].strip()

    return json.loads(first)


def fetch_comments(feedback_id):
    results = []
    cursor = None
    response_count = 0

    while True:
        r = session.post(
            GRAPHQL,
            headers={"x-fb-friendly-name": "CommentsListComponentsPaginationQuery"},
            data=comments_payload(feedback_id, cursor)
        )
        j = fb_json(r.text)
        
        # Save each JSON response for inspection
        response_count += 1
        # with open(f"response_{response_count}.json", "w", encoding="utf-8") as f:
        #     json.dump(j, f, ensure_ascii=False, indent=2)
        # print(f"💾 Saved response_{response_count}.json")
        
        comments_block = (
            j.get("data", {})
             .get("node", {})
             .get("comment_rendering_instance_for_feed_location", {})
             .get("comments", {})
        )

        edges = comments_block.get("edges", [])
        if not edges:
            break

        for e in edges:
            n = e["node"]
            fb = n["feedback"]

            results.append({
                "comment_id": n["legacy_fbid"],
                "author": n["author"]["name"],
                "text": (n.get("body") or {}).get("text", ""),
                "feedback_id": fb["id"],
                "expansion_token": fb["expansion_info"]["expansion_token"]
            })

        cursor = comments_block.get("page_info", {}).get("end_cursor")
        #break
        if not cursor:
            break

        time.sleep(0.4)

    return results

# ===== FETCH REPLIES =====

def fetch_replies(comment):
    r = session.post(
        GRAPHQL,
        headers={"x-fb-friendly-name": "Depth1CommentsListPaginationQuery"},
        data=replies_payload(comment["feedback_id"], comment["expansion_token"])
    )

    j = fb_json(r.text)
    replies = []

    edges = (
        j.get("data", {})
         .get("node", {})
         .get("replies_connection", {})
         .get("edges", [])
    )

    for e in edges:
        n = e["node"]
        replies.append({
            "reply_id": n["legacy_fbid"],
            "author": n["author"]["name"],
            "text": (n.get("body") or {}).get("text", "")

        })

    return replies

# ===== RUN =====

if __name__ == "__main__":
    POST_FEEDBACK_ID = "ZmVlZGJhY2s6MTQ1NTkzMDg2NjMyOTg1MQ=="

    all_data = []

    comments = fetch_comments(POST_FEEDBACK_ID)

    for c in comments:
        print(f"\n🗨️ {c['author']}: {c['text']}")
        c["replies"] = fetch_replies(c)

        for r in c["replies"]:
            print(f"   ↳ {r['author']}: {r['text']}")

        all_data.append(c)

    with open("comments.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print("\n✅ DONE — saved to comments.json")
