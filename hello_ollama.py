import datetime

def main():
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Hello Ollama from Gemma 4! Current time: {current_time}")
    
    print("\n--- Gemma 4 Encyclopedia ---")
    print("Model Name: Gemma 4")
    print("Key Characteristics:")
    print("- Model Size: Optimized for high performance across various scales (e.g., small, medium, and large versions).")
    print("- Context Length: Supports an expansive context window to handle long-form conversations and complex instructions.")
    print("- Nature: An open weights model designed for versatility and efficient deployment.")

if __name__ == "__main__":
    main()