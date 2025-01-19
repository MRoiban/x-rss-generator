from openai import OpenAI

client = OpenAI(base_url="http://localhost:15432", api_key="your_api_key")


def chat(prompt):
    """
    Sends a prompt to the LLM API and returns the response as a string.

    Args:
        prompt (str): The input prompt to send to the LLM.

    Returns:
        str: The response from the LLM.

    Raises:
        Exception: If the API request fails or returns an error.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Replace with your model's name
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise Exception(f"Failed to communicate with the LLM API: {e}") from e
