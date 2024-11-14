import time

import guardrails as gd
import openai
import streamlit as st

from src.cached_resources import (
    get_exact_match_cache,
    get_semantic_cache,
    get_guard, 
    instrument
)
from src.constants import OPENAI_MODEL_ARGUMENTS
from src.models import LLMResponse

st.set_page_config(page_title="SQL Code Generator")
st.title("SQL Code Generator")


def generate_response(
        input_text: str,
        cache,
        guard: gd.Guard,
        distance_threshold: float | None,
        cache_strategy: str
) -> None:
    """
    Generate a response for the given input text taking in the cache and guard.
    This function checks the cache for similar responses, and if none are found, it queris the LLM.
    """
    try:
        start_time = time.time()

        if cache_strategy == "Semantic Cache":
            cached_result = cache.check(
                prompt=input_text, distance_threshold=distance_threshold
            )
        else:
            cached_result = cache.get(input_text)
            if cached_result:
                cached_result = [{"response": cached_result.decode("utf-8")}]

        if not cached_result:
            (
                _,
                validated_response,
                _,
                validation_passed,
                error,
            ) = guard(
                openai.chat.completions.create,
                prompt_params={
                    "query": input_text,
                },
                **OPENAI_MODEL_ARGUMENTS,
            )
            total_time = time.time() - start_time

            if error or not validation_passed or not validated_response:
                st.error(f"Unable to produce an answer due to: {error}")
            else:
                valid_sql = LLMResponse(**validated_response)
                generated_sql = valid_sql.generated_sql
                st.info(generated_sql)
                st.info(f"That query took: {total_time:.2f}s")

                if cache_strategy == "Semantic Cache":
                    cache.store(
                        prompt=input_text,
                        response=generated_sql,
                        metadata={"generated_at": time.time()}
                    )
                else:
                    cache.set(input_text, generated_sql)
        else:
            total_time = (
                time.time() - start_time
            )
            st.info(cached_result[0]["response"])
            st.info(f"That query took: {total_time:.2f}s")

    except Exception as e:
        st.error(f"Error: {e}")


def main():
    cache_strategy = st.radio(
        "Select cache strategy:", ("Exact Match Cache", "Semantic Cache")
    )

    if cache_strategy == "Semantic Cache":
        distance_threshold = st.slider(
            "Select distance threshold for semantic cache:",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.01
        )
    else:
        distance_threshold = None

    guard = get_guard()
    cache = (
        get_semantic_cache()
        if cache_strategy == "Semantic Cache"
        else get_exact_match_cache()
    )
    instrument()
    with st.form("my_form"):
        st.warning("Our models can make mistakes!", icon="🚨")
        text = st.text_area(
            "Enter text:",
        )
        submitted = st.form_submit_button("Submit")
        if submitted:
            generate_response(text, cache, guard, distance_threshold, cache_strategy)


if __name__ == "__main__":
    main()
