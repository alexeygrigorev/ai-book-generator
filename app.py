import streamlit as st
from book_generator.plan import generate_text_plan_stream, refine_text_plan_stream, create_book_plan, save_plan
from pathlib import Path

st.set_page_config(page_title="AI Book Generator", layout="wide")
st.title("AI Book Generator Planner")

# Session state
for key, default in [("text_plan", None), ("structured_plan", None), ("messages", []), ("config", {}), ("total_cost", 0.0), ("generating", False)]:
    if key not in st.session_state:
        st.session_state[key] = default

# Sidebar
with st.sidebar:
    st.header("Book Configuration")
    topic = st.text_area("Book Topic", height=100, placeholder="e.g., Python for Data Science")
    size = st.selectbox("Book Size", ["Small (3-4 chapters, no parts)", "Medium (2-3 parts, 4-9 chapters)", "Large (4+ parts, 15 chapters)"])
    
    if st.button("Generate Initial Plan"):
        if not topic:
            st.error("Please enter a topic.")
        else:
            st.session_state.config = {"topic": topic, "size": size}
            st.session_state.generating = True
            st.session_state.text_plan = ""
            st.session_state.messages = []
            st.rerun()

# Streaming generation
if st.session_state.generating:
    st.header("Generating Plan...")
    placeholder = st.empty()
    
    try:
        full_text = ""
        for chunk in generate_text_plan_stream(st.session_state.config["topic"], st.session_state.config["size"]):
            if isinstance(chunk, tuple) and chunk[0] == "__DONE__":
                _,final_text, cost = chunk
                st.session_state.total_cost += cost
                st.session_state.text_plan = final_text
                st.session_state.messages = [{"role": "assistant", "content": f"Here's the initial plan:\n\n{final_text}\n\nFeel free to ask me to make changes!"}]
                st.session_state.generating = False
                st.rerun()
            else:
                full_text += chunk
                placeholder.markdown(full_text)
    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())
        st.session_state.generating = False

# Chat interface
elif st.session_state.text_plan:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("Chat & Refine")
        
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        if prompt := st.chat_input("Refine the plan"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("assistant"):
                placeholder = st.empty()
                try:
                    full_text = ""
                    for chunk in refine_text_plan_stream(st.session_state.text_plan, prompt):
                        if isinstance(chunk, tuple) and chunk[0] == "__DONE__":
                            _, final_text, cost = chunk
                            st.session_state.total_cost += cost
                            st.session_state.text_plan = final_text
                            st.session_state.messages.append({"role": "assistant", "content": f"Updated:\n\n{final_text}"})
                            placeholder.markdown(f"Updated:\n\n{final_text}")
                            import time
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            full_text += chunk
                            placeholder.markdown(full_text)
                except Exception as e:
                    st.error(f"Error: {e}")
        
        st.divider()
        st.metric("Total Cost", f"${st.session_state.total_cost:.4f}")
        
        if st.button("Ready - Create Structured Plan"):
            with st.spinner("Creating structured plan..."):
                try:
                    structured_plan, cost = create_book_plan(st.session_state.text_plan)
                    st.session_state.total_cost += cost
                    st.session_state.structured_plan = structured_plan
                    
                    slug = st.session_state.config["topic"].lower().replace(" ", "-")[:50]
                    path = Path("books") / slug
                    save_plan(structured_plan, path)
                    
                    st.success(f"✅ Saved to {path}/plan.yaml")
                    st.success(f"💰 Total: ${st.session_state.total_cost:.4f}")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    with col2:
        st.header("Current Plan")
        
        if st.session_state.structured_plan:
            st.subheader("Structured Plan (Saved)")
            st.json(st.session_state.structured_plan.model_dump())
        else:
            st.markdown(st.session_state.text_plan)

else:
    st.info("Configure the book on the left to get started.")
