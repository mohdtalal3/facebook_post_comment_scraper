"""Field extractors for Facebook Story nodes (counts, names, media checks)."""


def _first(*values):
    """Return the first non-None value."""
    for v in values:
        if v is not None:
            return v
    return None


def extract_page_name(node):
    try:
        actors = node.get("comet_sections", {}).get("content", {}).get("story", {}).get("actors", [])
        if actors:
            return actors[0].get("name")

        owning_profile = node.get("feedback", {}).get("owning_profile", {})
        if owning_profile:
            return owning_profile.get("name") or owning_profile.get("short_name")
    except Exception:
        pass
    return None


def extract_group_name(node):
    try:
        to_obj = (node.get("comet_sections", {})
                      .get("context_layout", {})
                      .get("story", {})
                      .get("comet_sections", {})
                      .get("title", {})
                      .get("story", {})
                      .get("to", {}))
        if to_obj.get("__typename") == "Group":
            return to_obj.get("name")

        target_group = (node.get("comet_sections", {})
                            .get("content", {})
                            .get("story", {})
                            .get("target_group", {}))
        if target_group.get("name"):
            return target_group.get("name")

        associated = node.get("feedback", {}).get("associated_group", {})
        if associated.get("name"):
            return associated.get("name")
    except Exception:
        pass
    return None


def extract_comment_count(node):
    """Comment count, checked across every known response shape."""
    try:
        count = (node.get("feedback", {})
                     .get("comment_rendering_instance", {})
                     .get("comments", {})
                     .get("total_count"))
        if count is not None:
            return count

        feedback_target = (node.get("comet_sections", {})
                               .get("feedback", {})
                               .get("story", {})
                               .get("story_ufi_container", {})
                               .get("story", {})
                               .get("feedback_context", {})
                               .get("feedback_target_with_context", {}))

        count = (feedback_target.get("comment_rendering_instance", {})
                                 .get("comments", {})
                                 .get("total_count"))
        if count is not None:
            return count

        comet_ufi = feedback_target.get("comet_ufi_summary_and_actions_renderer", {}).get("feedback", {})
        count = (comet_ufi.get("comment_rendering_instance", {})
                          .get("comments", {})
                          .get("total_count"))
        if count is not None:
            return count

        count = (comet_ufi.get("comments_count_summary_renderer", {})
                          .get("feedback", {})
                          .get("comment_rendering_instance", {})
                          .get("comments", {})
                          .get("total_count"))
        if count is not None:
            return count

        count = (node.get("feedback", {})
                     .get("comments_count_summary_renderer", {})
                     .get("feedback", {})
                     .get("comment_rendering_instance", {})
                     .get("comments", {})
                     .get("total_count"))
        if count is not None:
            return count
    except Exception:
        pass
    return 0


def extract_reaction_count(node):
    """Reaction count for a post, checked across known response shapes."""
    try:
        feedback = node.get("feedback", {})

        count = feedback.get("reactors", {}).get("count_reduced")
        if count is not None:
            return count

        feedback_target = (node.get("comet_sections", {})
                               .get("feedback", {})
                               .get("story", {})
                               .get("story_ufi_container", {})
                               .get("story", {})
                               .get("feedback_context", {})
                               .get("feedback_target_with_context", {}))

        comet_ufi = feedback_target.get("comet_ufi_summary_and_actions_renderer", {}).get("feedback", {})
        count = _first(
            comet_ufi.get("reactors", {}).get("count_reduced"),
            feedback_target.get("reactors", {}).get("count_reduced"),
            feedback.get("reaction_count", {}).get("count"),
        )
        if count is not None:
            return count
    except Exception:
        pass
    return 0


def extract_share_count(node):
    """Share count for a post (best effort)."""
    try:
        feedback = node.get("feedback", {})
        shares = feedback.get("shares")
        if isinstance(shares, dict) and shares.get("count") is not None:
            return shares["count"]

        feedback_target = (node.get("comet_sections", {})
                               .get("feedback", {})
                               .get("story", {})
                               .get("story_ufi_container", {})
                               .get("story", {})
                               .get("feedback_context", {})
                               .get("feedback_target_with_context", {}))
        comet_ufi = feedback_target.get("comet_ufi_summary_and_actions_renderer", {}).get("feedback", {})
        shares = comet_ufi.get("shares")
        if isinstance(shares, dict) and shares.get("count") is not None:
            return shares["count"]
    except Exception:
        pass
    return 0


def is_reel_or_video_post(node):
    """True when the Story node is a reel or video post."""
    if not node or node.get("__typename") != "Story":
        return False

    attachments = node.get("attachments", []) or []
    for att in attachments:
        media = att.get("media") or {}
        styles_media = (att.get("styles", {}) or {}).get("attachment", {}).get("media", {})

        for m in (media, styles_media):
            if m.get("__typename") == "Video" or "reel" in str(m).lower():
                return True

        for sub in att.get("all_subattachments", {}).get("nodes", []):
            m = sub.get("media") or {}
            if m.get("__typename") == "Video" or "reel" in str(m).lower():
                return True
    return False


def sanitize_name_folder(name):
    """Turn a page/group name into a safe folder name."""
    if not name:
        return None
    folder = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    return folder or "Unknown"
