
import json
import sys
from pathlib import Path


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def humanize_field(field_name):
    """Convert a profile key into a readable label."""
    return field_name.replace("_", " ").title()


def record_edit(profile, field_name):
    """Record a manual edit and return the profile to pending review."""

    review = profile.setdefault("review", {})

    manual_edits = review.setdefault("manual_edits", [])

    if field_name not in manual_edits:
        manual_edits.append(field_name)

    review["status"] = "pending"


def read_multiline_input(prompt):
    """
    Read multiple lines from the terminal.

    Type END to finish.
    Type CANCEL to discard the edit.
    """

    print(f"\n{prompt}")
    print("Enter your text below.")
    print("Type END on a separate line when finished.")
    print("Type CANCEL to discard the edit.\n")

    lines = []

    while True:
        line = input()

        command = line.strip().upper()

        if command == "END":
            return "\n".join(lines)

        if command == "CANCEL":
            return None

        lines.append(line)


# ---------------------------------------------------------
# PROFILE VALIDATION
# ---------------------------------------------------------

def validate_profile(profile):
    """Check whether the loaded JSON has the expected structure."""

    if not isinstance(profile, dict):
        raise ValueError("The profile must contain a JSON object.")

    if not isinstance(profile.get("research"), dict):
        raise ValueError("The profile is missing its research object.")

    if not isinstance(profile["research"].get("sections"), dict):
        raise ValueError("The profile is missing its sections object.")

    if not isinstance(profile.get("review"), dict):
        profile["review"] = {
            "status": "pending",
            "missing_fields": [],
        }

    return profile


# ---------------------------------------------------------
# MISSING FIELD TRACKING
# ---------------------------------------------------------

def update_missing_fields(profile):
    """Recalculate fields that have not been populated."""

    research = profile["research"]
    sections = research["sections"]

    missing_fields = []

    if not research.get("title"):
        missing_fields.append("title")

    if not research.get("authors"):
        missing_fields.append("authors")

    keywords = research.get("keywords") or {}

    if not keywords.get("items"):
        missing_fields.append("keywords")

    for section_name, section in sections.items():
        if section.get("status") != "found":
            missing_fields.append(section_name)

    profile["review"]["missing_fields"] = missing_fields

    return missing_fields


# ---------------------------------------------------------
# PROFILE DISPLAY
# ---------------------------------------------------------

def display_profile(profile):
    """Display the current research profile."""

    research = profile["research"]
    review = profile["review"]

    print("\n" + "=" * 60)
    print("             RESEARCH PROFILE")
    print("=" * 60)

    print("\nTITLE")
    print(research.get("title") or "Not available")

    print("\nAUTHORS")

    authors = research.get("authors") or []

    if authors:
        for index, author in enumerate(authors, start=1):
            print(f"{index}. {author}")
    else:
        print("No authors detected.")

    print("\nKEYWORDS")

    keywords = (research.get("keywords") or {}).get("items", [])

    if keywords:
        for keyword in keywords:
            print(f"- {keyword}")
    else:
        print("No keywords detected.")

    print("\nRESEARCH SECTIONS")

    for name, section in research["sections"].items():

        status = section.get("status", "not_found")
        pages = section.get("pages", [])

        print(f"\n{humanize_field(name)}")
        print(f"Status: {status}")

        if section.get("heading"):
            print(f"Detected heading: {', '.join(section['heading'])}")

        if pages:
            print(f"Pages: {pages}")

        print(f"Characters: {len(section.get('content', ''))}")

    print("\n" + "-" * 60)
    print("REVIEW INFORMATION")
    print("-" * 60)

    print("Status:", review.get("status", "pending"))

    missing_fields = update_missing_fields(profile)

    if missing_fields:
        print("\nFields not detected or not populated:")

        for field in missing_fields:
            print(f"- {humanize_field(field)}")

    else:
        print("\nAll profile fields have content.")

    manual_edits = review.get("manual_edits", [])

    if manual_edits:
        print("\nManually edited fields:")

        for field in manual_edits:
            print(f"- {humanize_field(field)}")

    print("\n" + "=" * 60)


# ---------------------------------------------------------
# EDIT TITLE
# ---------------------------------------------------------

def edit_title(profile):
    """Allow the researcher to edit the research title."""

    research = profile["research"]

    print("\n========== EDIT RESEARCH TITLE ==========")
    print("Current title:")
    print(research.get("title") or "Not available")

    new_title = input("\nEnter the new title (blank to cancel): ").strip()

    if not new_title:
        print("No changes made.")
        return False

    old_title = research.get("title")

    if old_title == new_title:
        print("The title is unchanged.")
        return False

    if "original_title" not in research:
        research["original_title"] = old_title

    research["title"] = new_title
    research["title_source"] = "manual"

    record_edit(profile, "title")

    print("Title updated.")

    return True


# ---------------------------------------------------------
# EDIT AUTHORS
# ---------------------------------------------------------

def edit_authors(profile):
    """Allow the researcher to replace the author list."""

    research = profile["research"]

    print("\n========== EDIT AUTHORS ==========")

    current_authors = research.get("authors") or []

    print("Current authors:")

    if current_authors:
        for author in current_authors:
            print(f"- {author}")
    else:
        print("No authors detected.")

    new_text = read_multiline_input(
        "Enter one author per line, including surname-first names."
    )

    if new_text is None:
        print("Author editing cancelled.")
        return False

    new_authors = [
        line.strip()
        for line in new_text.splitlines()
        if line.strip()
    ]

    if not new_authors and current_authors:
        confirm = input(
            "This will remove all authors. Continue? (y/N): "
        ).strip().casefold()

        if confirm != "y":
            print("No changes made.")
            return False

    if new_authors == current_authors:
        print("The author list is unchanged.")
        return False

    if "original_authors" not in research:
        research["original_authors"] = current_authors.copy()

    research["authors"] = new_authors
    research["authors_source"] = "manual"

    record_edit(profile, "authors")

    print(f"Updated {len(new_authors)} author(s).")

    return True


# ---------------------------------------------------------
# EDIT KEYWORDS
# ---------------------------------------------------------

def edit_keywords(profile):
    """Allow the researcher to replace the keyword list."""

    research = profile["research"]

    current_keyword_data = research.get("keywords") or {}

    current_keywords = current_keyword_data.get("items", [])

    print("\n========== EDIT KEYWORDS ==========")

    print("Current keywords:")

    if current_keywords:
        for keyword in current_keywords:
            print(f"- {keyword}")
    else:
        print("No keywords detected.")

    new_text = read_multiline_input(
        "Enter one keyword or phrase per line."
    )

    if new_text is None:
        print("Keyword editing cancelled.")
        return False

    new_keywords = [
        line.strip()
        for line in new_text.splitlines()
        if line.strip()
    ]

    if not new_keywords and current_keywords:
        confirm = input(
            "This will remove all keywords. Continue? (y/N): "
        ).strip().casefold()

        if confirm != "y":
            print("No changes made.")
            return False

    if new_keywords == current_keywords:
        print("The keywords are unchanged.")
        return False

    if "original_keywords" not in research:
        research["original_keywords"] = current_keyword_data.copy()

    research["keywords"] = {
        "items": new_keywords,
        "source": "manual" if new_keywords else None,
        "pages": [],
    }

    record_edit(profile, "keywords")

    print(f"Updated {len(new_keywords)} keyword(s).")

    return True


# ---------------------------------------------------------
# EDIT RESEARCH SECTION
# ---------------------------------------------------------

def edit_section(profile):
    """Allow the researcher to replace a section's content."""

    sections = profile["research"]["sections"]

    section_names = list(sections.keys())

    print("\n========== EDIT RESEARCH SECTION ==========")

    for index, name in enumerate(section_names, start=1):

        section = sections[name]

        print(
            f"{index}. {humanize_field(name)} "
            f"[{section.get('status', 'not_found')}]"
        )

    print("0. Cancel")

    choice = input("\nSelect a section to edit: ").strip()

    if choice == "0":
        return False

    if not choice.isdigit():
        print("Invalid selection.")
        return False

    selected_index = int(choice) - 1

    if selected_index < 0 or selected_index >= len(section_names):
        print("Invalid selection.")
        return False

    section_name = section_names[selected_index]
    section = sections[section_name]

    current_content = section.get("content", "")

    print(f"\n========== {humanize_field(section_name).upper()} ==========")

    print("\nCurrent content preview:")

    if current_content:
        print(current_content[:600])

        if len(current_content) > 600:
            print("\n[Preview shortened]")
    else:
        print("No content detected.")

    new_content = read_multiline_input(
        "Enter the corrected section content."
    )

    if new_content is None:
        print("Section editing cancelled.")
        return False

    if new_content == current_content:
        print("The section content is unchanged.")
        return False

    if "original_content" not in section:
        section["original_content"] = current_content

    section["content"] = new_content
    section["content_source"] = "manual"

    if new_content.strip():
        section["status"] = "found"
    elif section.get("heading"):
        section["status"] = "heading_found_no_content"
    else:
        section["status"] = "not_found"

    # Keep original page references as provenance for the
    # extracted version. Manual content is separately identified.
    record_edit(profile, section_name)

    print(f"{humanize_field(section_name)} updated.")

    return True


# ---------------------------------------------------------
# SAVE PROFILE
# ---------------------------------------------------------

def get_output_path(source_path):
    """
    Save a reviewed profile separately from its extracted version.

    Reopening an already reviewed profile updates that same file.
    """

    if source_path.stem.endswith("_reviewed"):
        return source_path

    return source_path.with_name(
        f"{source_path.stem}_reviewed.json"
    )


def save_profile(profile, output_path, approved=False):
    """Save the profile safely as formatted JSON."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    update_missing_fields(profile)

    profile["review"]["status"] = (
        "approved" if approved else "pending"
    )

    # Write to a temporary file first to reduce the chance
    # of leaving a partially written JSON file.
    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )

    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(
                profile,
                file,
                indent=4,
                ensure_ascii=False
            )

        temporary_path.replace(output_path)

    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    print("\nProfile saved successfully.")
    print("Review status:", profile["review"]["status"])
    print("Saved to:", output_path)


# ---------------------------------------------------------
# TERMINAL EDITOR
# ---------------------------------------------------------

def run_profile_editor(profile, source_path):
    """Run the interactive research profile review workflow."""

    output_path = get_output_path(source_path)

    dirty = False

    while True:

        print("\n" + "=" * 55)
        print("          RESEARCH PROFILE REVIEW")
        print("=" * 55)

        print("1. View research profile")
        print("2. Edit research title")
        print("3. Edit authors")
        print("4. Edit keywords")
        print("5. Edit research section")
        print("6. Save draft")
        print("7. Approve and save profile")
        print("0. Exit")

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            display_profile(profile)

        elif choice == "2":
            if edit_title(profile):
                dirty = True

        elif choice == "3":
            if edit_authors(profile):
                dirty = True

        elif choice == "4":
            if edit_keywords(profile):
                dirty = True

        elif choice == "5":
            if edit_section(profile):
                dirty = True

        elif choice == "6":
            save_profile(
                profile,
                output_path,
                approved=False
            )
            dirty = False

        elif choice == "7":

            display_profile(profile)

            print(
                "\nYou are confirming that you have reviewed "
                "the research profile."
            )

            confirmation = input(
                "Approve and save this profile? (y/N): "
            ).strip().casefold()

            if confirmation == "y":
                save_profile(
                    profile,
                    output_path,
                    approved=True
                )
                dirty = False
            else:
                print("Approval cancelled.")

        elif choice == "0":

            if dirty:
                confirmation = input(
                    "\nYou have unsaved changes. Exit without saving? (y/N): "
                ).strip().casefold()

                if confirmation != "y":
                    continue

            print("Exiting profile editor.")
            break

        else:
            print("Invalid option. Please try again.")


# ---------------------------------------------------------
# APPLICATION ENTRY POINT
# ---------------------------------------------------------

def main():

    if len(sys.argv) >= 2:
        source_path = Path(sys.argv[1]).expanduser()
    else:
        entered_path = input(
            "Enter the research profile JSON path: "
        ).strip()

        if not entered_path:
            print("No file path supplied.")
            return

        source_path = Path(entered_path).expanduser()

    if not source_path.exists():
        print(f"Profile file not found: {source_path}")
        return

    if not source_path.is_file():
        print("The supplied path is not a file.")
        return

    if source_path.suffix.lower() != ".json":
        print("The supplied file must be a JSON file.")
        return

    try:
        with source_path.open("r", encoding="utf-8") as file:
            profile = json.load(file)

        profile = validate_profile(profile)

        run_profile_editor(profile, source_path)

    except json.JSONDecodeError as error:
        print(f"Invalid JSON file: {error}")

    except (OSError, ValueError) as error:
        print(f"Unable to open profile: {error}")


if __name__ == "__main__":
    main()
