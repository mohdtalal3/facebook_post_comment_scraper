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


def _deep_get(obj, target_key, sub_key, max_depth=14):
    """Recursively find obj.**.{target_key}.{sub_key} anywhere in a nested structure.

    Facebook moves these fields around between response versions, so after the
    known paths fail we search the whole subtree.
    """
    if max_depth < 0:
        return None
    if isinstance(obj, dict):
        target = obj.get(target_key)
        if isinstance(target, dict):
            val = target.get(sub_key)
            if val is not None:
                return val
        for v in obj.values():
            found = _deep_get(v, target_key, sub_key, max_depth - 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_get(item, target_key, sub_key, max_depth - 1)
            if found is not None:
                return found
    return None


def extract_reaction_count(node):
    """Reaction count for a post. Prefers the exact integer count over the
    localized i18n string ("4.1K"). Paths verified against live responses."""
    try:
        feedback = node.get("feedback") or {}

        feedback_target = (node.get("comet_sections", {})
                               .get("feedback", {})
                               .get("story", {})
                               .get("story_ufi_container", {})
                               .get("story", {})
                               .get("feedback_context", {})
                               .get("feedback_target_with_context", {}))

        comet_ufi = feedback_target.get("comet_ufi_summary_and_actions_renderer", {}).get("feedback", {})

        count = _first(
            comet_ufi.get("reaction_count", {}).get("count"),
            feedback.get("reaction_count", {}).get("count"),
            comet_ufi.get("i18n_reaction_count"),
            feedback.get("i18n_reaction_count"),
            comet_ufi.get("reactors", {}).get("count_reduced"),
            feedback.get("reactors", {}).get("count_reduced"),
        )
        if count is not None:
            return count

        # Fallback: search anywhere in the node (unknown response shapes)
        count = _deep_get(node, "reaction_count", "count")
        if count is not None:
            return count
        count = _deep_get(node, "reactors", "count_reduced")
        if count is not None:
            return count
    except Exception:
        pass
    return 0


def extract_share_count(node):
    """Share count for a post. Prefers the exact integer count."""
    try:
        feedback = node.get("feedback") or {}

        feedback_target = (node.get("comet_sections", {})
                               .get("feedback", {})
                               .get("story", {})
                               .get("story_ufi_container", {})
                               .get("story", {})
                               .get("feedback_context", {})
                               .get("feedback_target_with_context", {}))
        comet_ufi = feedback_target.get("comet_ufi_summary_and_actions_renderer", {}).get("feedback", {})

        count = _first(
            comet_ufi.get("share_count", {}).get("count"),
            feedback.get("share_count", {}).get("count"),
            comet_ufi.get("i18n_share_count"),
            feedback.get("i18n_share_count"),
        )
        if count is not None:
            return count

        count = _deep_get(node, "share_count", "count")
        if count is not None:
            return count
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
