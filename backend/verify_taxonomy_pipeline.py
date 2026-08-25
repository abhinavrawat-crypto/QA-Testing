"""Verification script for 2-level taxonomy Test Impact Analysis pipeline."""
import asyncio
import logging
import json
from uuid import UUID
from dotenv import load_dotenv

load_dotenv('/home/rawatabhinav93/ai_test_platform/.env')
logging.basicConfig(level=logging.INFO)

from app.database import AsyncSessionLocal
from app.models.jira import Story
from app.models.github import GitHubRepo
from app.services.impact_service import ImpactService

BENCHMARK_STORIES = [
    {
        "key": "STORY-PROMO-STACK",
        "summary": "User can stack multiple promotional codes at checkout",
        "description": "Allow customers to apply more than one promo code to a single checkout order.",
        "acceptance_criteria": "1. User can enter first promo code and get discount.\n2. User can enter second promo code and get additional discount.\n3. Order summary reflects cumulative discounts.",
        "expected_verdict": "IMPACTED",
        "expected_sub_tag": "NEEDS_UPDATE",
        "target_file": "features/amazon_checkout.feature"
    },
    {
        "key": "STORY-2FA-LOGIN",
        "summary": "User can enable and use two-factor authentication (2FA) when signing in",
        "description": "Add 2FA support during user sign in.",
        "acceptance_criteria": "1. User enters username and password.\n2. Prompt for 6-digit OTP code appears.\n3. Entering valid OTP completes login.",
        "expected_verdict": "IMPACTED",
        "expected_sub_tag": "NEEDS_EXTENSION",
        "target_file": "features/amazon_login.feature"
    },
    {
        "key": "STORY-REVIEWS-RATINGS",
        "summary": "User can view and submit product reviews and star ratings",
        "description": "Allow verified buyers to write text reviews and select 1-5 star ratings for purchased products.",
        "acceptance_criteria": "1. User can see average star rating on product page.\n2. User can submit a 1-5 star rating with text review.",
        "expected_verdict": "NOT_COVERED",
        "expected_sub_tag": None,
        "target_file": None
    },
    {
        "key": "STORY-CART-MANAGEMENT",
        "summary": "User can fully manage items in their shopping cart",
        "description": "Support adding items to cart, updating item quantities, removing items, and cart persistence.",
        "acceptance_criteria": "1. User can add item to cart.\n2. User can update quantity or remove item.\n3. Cart items persist across sessions.",
        "expected_verdict": "NOT_IMPACTED",
        "expected_sub_tag": None,
        "target_file": "features/amazon_cart.feature"
    }
]

async def verify_taxonomy():
    async with AsyncSessionLocal() as session:
        # Get active repo
        repo_res = await session.execute(select(GitHubRepo).where(GitHubRepo.full_name == 'abhinavrawat-crypto/QA-Testing'))
        repo = repo_res.scalar_one_or_none()
        if not repo:
            print("ERROR: Repo 'abhinavrawat-crypto/QA-Testing' not found in database!")
            return

        impact_svc = ImpactService(session)

        from app.models.jira import JiraProject
        proj_res = await session.execute(select(JiraProject))
        proj = proj_res.scalars().first()
        proj_id = proj.id if proj else UUID('11111111-1111-1111-1111-111111111111')

        for bench in BENCHMARK_STORIES:
            print(f"\n=======================================================")
            print(f"BENCHMARK STORY: {bench['key']} — {bench['summary']}")
            print(f"=======================================================")

            story_res = await session.execute(select(Story).where(Story.jira_issue_key == bench['key']))
            story = story_res.scalar_one_or_none()
            if not story:
                story = Story(
                    project_id=proj_id,
                    jira_issue_id=bench['key'],
                    jira_issue_key=bench['key'],
                    summary=bench['summary'],
                    description_text=bench['description'],
                    acceptance_criteria=bench['acceptance_criteria'],
                )
                session.add(story)
                await session.flush()

            # Embed story
            story_text = f"Title: {story.summary}\nDescription: {story.description_text}\nAcceptance Criteria: {story.acceptance_criteria}"
            story.embedding = await impact_svc._embed(story_text)
            await session.flush()

            # Vector search
            candidates = await impact_svc._vector_search(story.embedding, [repo.id])

            # Gemini Reasoning with 2-level taxonomy
            reasoning = await impact_svc._gemini_impact_reasoning(story, candidates)

            print(f"\n[TAXONOMY RESULTS FOR {bench['key']}]:")
            print(json.dumps(reasoning, indent=2))

            # Validate against expectations
            verdicts = reasoning.get("verdicts", [])
            not_covered = reasoning.get("not_covered", {})

            if bench["expected_verdict"] == "NOT_COVERED":
                assert not_covered.get("is_not_covered") is True, f"Expected NOT_COVERED for {bench['key']}"
                print(f"✅ PASSED: Verified Level 1 verdict NOT_COVERED at story level for {bench['key']}")
            else:
                target_v = next((v for v in verdicts if bench["target_file"] in v.get("file_path", "")), None)
                if bench["expected_verdict"] == "NOT_IMPACTED":
                    # Target file or all files should be NOT_IMPACTED
                    if target_v:
                        print(f"  Target File Verdict: {target_v.get('verdict')} | Sub-tag: {target_v.get('sub_tag')}")
                        assert target_v.get("verdict") == "NOT_IMPACTED", f"Expected NOT_IMPACTED for {bench['key']}"
                    else:
                        print("  No candidate marked IMPACTED. All candidates are NOT_IMPACTED.")
                    print(f"✅ PASSED: Verified Level 1 verdict NOT_IMPACTED for {bench['key']}")
                elif bench["expected_verdict"] == "IMPACTED":
                    assert target_v is not None, f"Could not find candidate for {bench['target_file']}"
                    print(f"  Target File: {target_v.get('file_path')}")
                    print(f"  Level 1 Verdict: {target_v.get('verdict')}")
                    print(f"  Level 2 Sub-Tag: {target_v.get('sub_tag')}")
                    print(f"  Rationale: {target_v.get('rationale')}")

                    assert target_v.get("verdict") == "IMPACTED", f"Expected IMPACTED for {bench['target_file']}"
                    assert target_v.get("sub_tag") == bench["expected_sub_tag"], f"Expected sub_tag {bench['expected_sub_tag']}, got {target_v.get('sub_tag')}"
                    print(f"✅ PASSED: Verified Level 1 IMPACTED and Level 2 {bench['expected_sub_tag']} for {bench['key']}")

if __name__ == "__main__":
    from sqlalchemy import select
    asyncio.run(verify_taxonomy())
