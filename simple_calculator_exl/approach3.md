At 150,000 characters, your file is roughly 35,000 to 40,000 tokens. While modern models have massive context windows that can easily read the entire file at once, the bottleneck is the **output limit**. If you ask an LLM to return the fully parsed, deduplicated, and formatted markdown for all skills in a single prompt, it will likely hit its output token limit (usually 4k to 8k tokens) and cut off halfway through.
To handle a document of this size effectively, you need a **Two-Pass "Index and Extract" Strategy**.
Instead of asking the model to do everything at once, you use the LLM first to map the document, and then to extract the content piece by piece. Here is how you can build this using Python and the Gemini API.
### The Two-Pass Extraction Strategy
**Pass 1: Build the Index (Small Output)**
You send the entire 150k-character document to the model with a very specific prompt: ask it *only* to identify the unique skills and resolve the duplicates into a clean list.
**Pass 2: Targeted Extraction (Iterative Output)**
Once you have the list of unique skills, you write a script that loops through that list. For each skill, you send the original document back to the model and ask it to extract, merge, and format *only* the content related to that specific skill.
### Implementation Example
Here is a Python script utilizing the genai.Client to automate this two-pass process. It uses structured outputs to ensure you get a clean, iterable list in the first pass.
```python
import os
from google import genai
from pydantic import BaseModel

# Define the expected structure for Pass 1
class SkillIndex(BaseModel):
    skills: list[str]

def split_large_markdown(file_path):
    # Initialize the Gemini client
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # Read the 150,000 character file
    with open(file_path, 'r', encoding='utf-8') as f:
        document_content = f.read()

    print("Pass 1: Identifying unique skills...")
    
    # Prompt 1: Get the deduplicated index
    index_prompt = """
    Analyze the following markdown document. Identify all the distinct technical skills being described. 
    Resolve any duplicates or synonyms (e.g., if 'Python' and 'Python Programming' appear, just list 'Python').
    """
    
    index_response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=[index_prompt, document_content],
        config={
            'response_mime_type': 'application/json',
            'response_schema': SkillIndex,
            'temperature': 0.1
        }
    )
    
    unique_skills = index_response.parsed.skills
    print(f"Found {len(unique_skills)} unique skills: {unique_skills}")

    print("\nPass 2: Extracting and merging content for each skill...")
    
    for skill in unique_skills:
        print(f"Processing: {skill}...")
        
        # Prompt 2: Extract and merge content for a single skill
        extraction_prompt = f"""
        You are an expert technical editor. Read the attached markdown document and extract all information related to the skill: "{skill}".
        
        Instructions:
        1. Find all sections, paragraphs, or bullet points related to "{skill}".
        2. Merge any duplicate information seamlessly.
        3. Format the output as a clean, standalone markdown file starting with an H1 tag for the skill.
        4. Do not include information about other skills.
        """
        
        content_response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=[extraction_prompt, document_content],
            config={'temperature': 0.2}
        )
        
        # Save the result to a new file
        safe_filename = skill.lower().replace(' ', '_').replace('/', '_') + "_skill.md"
        with open(safe_filename, 'w', encoding='utf-8') as f:
            f.write(content_response.text)
            
    print("Done! All skills extracted to individual files.")

# Run the script
# split_large_markdown('your_large_parent_file.md')

```
### Why this works best for large files:
 * **Bypasses Output Limits:** By only asking for one skill's content at a time, you ensure the LLM never truncates your generated markdown files.
 * **Excellent Deduplication:** Because the model reads the whole file during extraction, if "Docker" is mentioned on page 1 and page 40, the model will combine both sections logically into docker_skill.md.
 * **Context Preservation:** Since modern models cache input tokens efficiently, sending the large document multiple times in Pass 2 is fast and relatively inexpensive.
Do you want to refine the extraction prompt in the script to format the resulting skill.md files in a specific way, such as enforcing a standard structure (e.g., Overview, Prerequisites, Examples)?
