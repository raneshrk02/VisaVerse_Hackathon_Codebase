"""
NCERT RAG Assistant GUI

This module provides a modern tkinter-based graphical user interface for the
SAGE RAG system with comprehensive features including async processing,
error handling, and user-friendly interactions.

Features:
- Clean, modern interface with proper styling
- Async query processing with progress updates
- Collapsible sections for sources
- Export functionality and clipboard operations
- Comprehensive error handling and startup checks
- Threading to prevent GUI freezing
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import time
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
from datetime import datetime

from .config_loader import ConfigLoader
from .rag_pipeline import RAGPipeline, RAGResponse


class LoadingScreen:
    """Loading screen for application initialization."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NCERT RAG Assistant - Loading")
        self.root.geometry("400x200")
        self.root.resizable(False, False)
        
        # Center the window
        self.root.eval('tk::PlaceWindow . center')
        
        # Configure style
        self.root.configure(bg='#f0f0f0')
        
        # Main frame
        main_frame = tk.Frame(self.root, bg='#f0f0f0', padx=30, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(
            main_frame,
            text="NCERT RAG Assistant",
            font=('Arial', 16, 'bold'),
            bg='#f0f0f0',
            fg='#2c3e50'
        )
        title_label.pack(pady=(0, 20))
        
        # Progress bar
        self.progress = ttk.Progressbar(
            main_frame,
            mode='indeterminate',
            length=300
        )
        self.progress.pack(pady=(0, 10))
        
        # Status label
        self.status_label = tk.Label(
            main_frame,
            text="Initializing...",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#7f8c8d'
        )
        self.status_label.pack()
        
        # Start progress animation
        self.progress.start(10)
    
    def update_status(self, message: str):
        """Update the status message."""
        self.status_label.config(text=message)
        self.root.update()
    
    def close(self):
        """Close the loading screen."""
        self.progress.stop()
        self.root.destroy()


class CollapsibleFrame:
    """A collapsible frame widget."""
    
    def __init__(self, parent, title: str, bg_color: str = '#f8f9fa'):
        self.parent = parent
        self.title = title
        self.is_expanded = False
        
        # Main frame
        self.frame = tk.Frame(parent, bg=bg_color, relief=tk.RIDGE, bd=1)
        
        # Header frame (clickable)
        self.header_frame = tk.Frame(self.frame, bg='#e9ecef', cursor='hand2')
        self.header_frame.pack(fill=tk.X, padx=2, pady=2)
        
        # Arrow and title
        self.arrow_label = tk.Label(
            self.header_frame,
            text="▶",
            font=('Arial', 10),
            bg='#e9ecef',
            fg='#495057'
        )
        self.arrow_label.pack(side=tk.LEFT, padx=(5, 2))
        
        self.title_label = tk.Label(
            self.header_frame,
            text=title,
            font=('Arial', 10, 'bold'),
            bg='#e9ecef',
            fg='#495057'
        )
        self.title_label.pack(side=tk.LEFT, padx=(2, 5))
        
        # Content frame (initially hidden)
        self.content_frame = tk.Frame(self.frame, bg=bg_color)
        
        # Bind click events
        self.header_frame.bind("<Button-1>", self.toggle)
        self.arrow_label.bind("<Button-1>", self.toggle)
        self.title_label.bind("<Button-1>", self.toggle)
    
    def toggle(self, event=None):
        """Toggle the expanded/collapsed state."""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()
    
    def expand(self):
        """Expand the frame to show content."""
        self.is_expanded = True
        self.arrow_label.config(text="▼")
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
    
    def collapse(self):
        """Collapse the frame to hide content."""
        self.is_expanded = False
        self.arrow_label.config(text="▶")
        self.content_frame.pack_forget()
    
    def pack(self, **kwargs):
        """Pack the main frame."""
        self.frame.pack(**kwargs)
    
    def get_content_frame(self):
        """Get the content frame for adding widgets."""
        return self.content_frame


class NCERTRAGAssistantGUI:
    """Main GUI application for NCERT RAG Assistant."""
    
    def __init__(self):
        self.root = None
        self.rag_pipeline = None
        self.conversation_history = []
        self.current_response = None
        
        # Threading
        self.processing = False
        self.current_thread = None
        
        # GUI components (will be initialized in create_gui)
        self.class_var = None
        self.question_text = None
        self.answer_text = None
        self.status_var = None
        self.ask_button = None
        self.clear_button = None
        self.copy_button = None
        self.export_button = None
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """Main entry point to run the application."""
        loading_screen = LoadingScreen()
        
        try:
            # Initialize the application
            loading_screen.update_status("Loading configuration...")
            config = self._load_config()
            
            loading_screen.update_status("Initializing RAG pipeline...")
            self.rag_pipeline = self._initialize_rag_pipeline(config)
            
            loading_screen.update_status("Creating user interface...")
            self._create_gui()
            
            loading_screen.update_status("Ready!")
            time.sleep(0.5)  # Brief pause to show "Ready!" message
            
        except Exception as e:
            loading_screen.close()
            messagebox.showerror(
                "Initialization Error",
                f"Failed to initialize NCERT RAG Assistant:\n\n{str(e)}\n\n"
                "Please check your configuration and try again."
            )
            return
        
        # Close loading screen and show main window
        loading_screen.close()
        
        # Start main application
        self.root.deiconify()  # Show the main window
        self.root.mainloop()
    
    def _load_config(self) -> Any:
        """Load application configuration."""
        try:
            config_loader = ConfigLoader("config.yaml")
            config = config_loader.load_config()
            return config
        except Exception as e:
            raise Exception(f"Configuration loading failed: {e}")
    
    def _initialize_rag_pipeline(self, config) -> RAGPipeline:
        """Initialize the RAG pipeline with startup checks."""
        try:
            # Check ChromaDB path
            chroma_path = Path(config.chromadb.persist_directory)
            if not chroma_path.exists():
                chroma_path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created ChromaDB directory: {chroma_path}")
            
            # Check model path
            model_path = Path(config.llm.model_path)
            if not model_path.exists():
                raise FileNotFoundError(
                    f"Model file not found: {model_path}\n\n"
                    "Please download the Phi-2 GGUF model and place it in the models directory."
                )
            
            # Initialize pipeline
            pipeline = RAGPipeline(config)
            
            # Test basic functionality
            test_stats = pipeline.get_collection_stats()
            self.logger.info(f"Pipeline initialized successfully. Collections: {len(test_stats)}")
            
            return pipeline
            
        except Exception as e:
            raise Exception(f"RAG pipeline initialization failed: {e}")
    
    def _create_gui(self):
        """Create the main GUI interface."""
        # Create main window (initially hidden)
        self.root = tk.Tk()
        self.root.title("NCERT RAG Assistant")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        self.root.withdraw()  # Hide initially
        
        # Configure style
        self._configure_styles()
        
        # Create main layout
        self._create_main_layout()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Center window
        self.root.eval('tk::PlaceWindow . center')
    
    def _configure_styles(self):
        """Configure modern styling for the application."""
        style = ttk.Style()
        
        # Configure ttk styles
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground='#2c3e50')
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), foreground='#34495e')
        style.configure('Info.TLabel', font=('Arial', 10), foreground='#7f8c8d')
        style.configure('Success.TLabel', font=('Arial', 10), foreground='#27ae60')
        style.configure('Warning.TLabel', font=('Arial', 10), foreground='#f39c12')
        style.configure('Error.TLabel', font=('Arial', 10), foreground='#e74c3c')
        
        # Configure button styles
        style.configure('Primary.TButton', font=('Arial', 10, 'bold'))
        style.configure('Secondary.TButton', font=('Arial', 9))
        
        # Root window styling
        self.root.configure(bg='#ffffff')
    
    def _create_main_layout(self):
        """Create the main application layout."""
        # Main container with padding
        main_container = tk.Frame(self.root, bg='#ffffff')
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_label = ttk.Label(
            main_container,
            text="NCERT RAG Assistant",
            style='Title.TLabel'
        )
        title_label.pack(pady=(0, 20))
        
        # Input section
        self._create_input_section(main_container)
        
        # Action buttons
        self._create_action_buttons(main_container)
        
        # Output section
        self._create_output_section(main_container)
        
        # Status bar
        self._create_status_bar(main_container)
    
    def _create_input_section(self, parent):
        """Create the input section with class selection and question entry."""
        input_frame = tk.Frame(parent, bg='#ffffff')
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Class selection
        class_frame = tk.Frame(input_frame, bg='#ffffff')
        class_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(class_frame, text="Select Class:", style='Heading.TLabel').pack(side=tk.LEFT)
        
        self.class_var = tk.StringVar(value="All Classes")
        class_options = ["All Classes"] + [f"Class {i}" for i in range(1, 13)]
        class_combo = ttk.Combobox(
            class_frame,
            textvariable=self.class_var,
            values=class_options,
            state="readonly",
            width=15,
            font=('Arial', 10)
        )
        class_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        # Add callback to track selection changes
        def on_class_change(*args):
            current_selection = self.class_var.get()
            print(f"DEBUG: Class dropdown changed to: '{current_selection}'")
        
        # Bind both StringVar trace and combobox selection event
        self.class_var.trace('w', on_class_change)
        class_combo.bind('<<ComboboxSelected>>', lambda event: on_class_change())
        
        # Store reference to combo for debugging
        self.class_combo = class_combo
        
        # Question input
        question_frame = tk.Frame(input_frame, bg='#ffffff')
        question_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(question_frame, text="Your Question:", style='Heading.TLabel').pack(anchor=tk.W)
        
        # Question text widget with frame for border
        question_container = tk.Frame(question_frame, relief=tk.SUNKEN, bd=1)
        question_container.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.question_text = tk.Text(
            question_container,
            height=3,
            wrap=tk.WORD,
            font=('Arial', 11),
            bg='#f8f9fa',
            fg='#495057',
            insertbackground='#495057',
            selectbackground='#007bff',
            selectforeground='white',
            relief=tk.FLAT,
            padx=10,
            pady=8
        )
        self.question_text.pack(fill=tk.BOTH, expand=True)
        
        # Placeholder text
        self._add_placeholder_to_question()
    
    def _add_placeholder_to_question(self):
        """Add placeholder text to question input."""
        placeholder = "Enter your question here... (e.g., 'What is photosynthesis?')"
        self.question_text.insert('1.0', placeholder)
        self.question_text.config(fg='#adb5bd')
        
        def on_focus_in(event):
            if self.question_text.get('1.0', tk.END).strip() == placeholder:
                self.question_text.delete('1.0', tk.END)
                self.question_text.config(fg='#495057')
        
        def on_focus_out(event):
            if not self.question_text.get('1.0', tk.END).strip():
                self.question_text.insert('1.0', placeholder)
                self.question_text.config(fg='#adb5bd')
        
        self.question_text.bind('<FocusIn>', on_focus_in)
        self.question_text.bind('<FocusOut>', on_focus_out)
    
    def _create_action_buttons(self, parent):
        """Create action buttons."""
        button_frame = tk.Frame(parent, bg='#ffffff')
        button_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Primary buttons
        primary_frame = tk.Frame(button_frame, bg='#ffffff')
        primary_frame.pack(side=tk.LEFT)
        
        self.ask_button = ttk.Button(
            primary_frame,
            text="Ask Question",
            command=self._on_ask_question,
            style='Primary.TButton',
            width=15
        )
        self.ask_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_button = ttk.Button(
            primary_frame,
            text="Clear",
            command=self._on_clear,
            style='Secondary.TButton',
            width=10
        )
        self.clear_button.pack(side=tk.LEFT)
        
        # Secondary buttons
        secondary_frame = tk.Frame(button_frame, bg='#ffffff')
        secondary_frame.pack(side=tk.RIGHT)
        
        self.export_button = ttk.Button(
            secondary_frame,
            text="Export History",
            command=self._on_export_history,
            style='Secondary.TButton',
            width=12
        )
        self.export_button.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.copy_button = ttk.Button(
            secondary_frame,
            text="Copy Answer",
            command=self._on_copy_answer,
            style='Secondary.TButton',
            width=12,
            state=tk.DISABLED
        )
        self.copy_button.pack(side=tk.RIGHT)
    
    def _create_output_section(self, parent):
        """Create the output section with answer display and collapsible sections."""
        output_frame = tk.Frame(parent, bg='#ffffff')
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        # Answer section
        answer_label = ttk.Label(output_frame, text="Answer:", style='Heading.TLabel')
        answer_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Answer text with scrollbar
        answer_container = tk.Frame(output_frame, relief=tk.SUNKEN, bd=1)
        answer_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.answer_text = scrolledtext.ScrolledText(
            answer_container,
            height=15,
            wrap=tk.WORD,
            font=('Arial', 11),
            bg='#ffffff',
            fg='#2c3e50',
            relief=tk.FLAT,
            padx=15,
            pady=10,
            state=tk.DISABLED,
            selectbackground='#007bff',
            selectforeground='white'
        )
        self.answer_text.pack(fill=tk.BOTH, expand=True)
        
        # Collapsible sections container
        self.collapsible_container = tk.Frame(output_frame, bg='#ffffff')
        self.collapsible_container.pack(fill=tk.X, pady=(0, 10))
    
    def _create_status_bar(self, parent):
        """Create the status bar."""
        status_frame = tk.Frame(parent, bg='#e9ecef', relief=tk.SUNKEN, bd=1)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            style='Info.TLabel',
            background='#e9ecef'
        )
        status_label.pack(side=tk.LEFT, padx=10, pady=5)
    
    def _get_question_text(self) -> str:
        """Get the current question text, handling placeholder."""
        text = self.question_text.get('1.0', tk.END).strip()
        placeholder = "Enter your question here... (e.g., 'What is photosynthesis?')"
        
        if text == placeholder or self.question_text.cget('fg') == '#adb5bd':
            return ""
        
        return text
    
    def _get_class_number(self) -> Optional[int]:
        """Extract class number from selection."""
        # Force update the widget to ensure we get the current value
        self.root.update_idletasks()
        
        # Try getting value from StringVar first
        class_text = self.class_var.get()
        print(f"DEBUG: Raw class_text from StringVar: '{class_text}'")
        
        # As a fallback, try getting directly from combobox
        if hasattr(self, 'class_combo'):
            combo_value = self.class_combo.get()
            print(f"DEBUG: Direct combobox value: '{combo_value}'")
            if combo_value and combo_value != class_text:
                print(f"DEBUG: StringVar and combobox mismatch! Using combobox value: '{combo_value}'")
                class_text = combo_value
                # Update StringVar to match
                self.class_var.set(combo_value)
        
        if class_text == "All Classes":
            print(f"DEBUG: All Classes selected - will search across all collections")
            return None
        
        if not class_text or not class_text.startswith("Class "):
            print(f"DEBUG: Invalid class_text format: '{class_text}', defaulting to All Classes")
            return None
        
        try:
            class_num = int(class_text.split()[-1])
            print(f"DEBUG: Selected class text: '{class_text}', extracted number: {class_num}")
            return class_num
        except (ValueError, IndexError) as e:
            print(f"DEBUG: Error parsing class number from '{class_text}': {e}")
            return None
    
    def _validate_input(self) -> bool:
        """Validate user input."""
        question = self._get_question_text()
        
        if not question:
            messagebox.showwarning("Input Required", "Please enter a question.")
            self.question_text.focus()
            return False
        
        if len(question) > 1000:
            messagebox.showwarning(
                "Question Too Long",
                "Please keep your question under 1000 characters."
            )
            return False
        
        return True
    
    def _on_ask_question(self):
        """Handle ask question button click."""
        if self.processing:
            return
        
        if not self._validate_input():
            return
        
        # Start processing in background thread
        question = self._get_question_text()
        
        # Add debugging before getting class number
        print(f"DEBUG: About to get class number...")
        print(f"DEBUG: Current dropdown StringVar value: '{self.class_var.get()}'")
        
        class_num = self._get_class_number()
        
        print(f"DEBUG: Final class_num to be processed: {class_num}")
        
        self.current_thread = threading.Thread(
            target=self._process_question_async,
            args=(question, class_num),
            daemon=True
        )
        self.current_thread.start()
    
    def _process_question_async(self, question: str, class_num: int):
        """Process question in background thread."""
        try:
            self.processing = True
            
            # Update UI for processing state
            self.root.after(0, self._enter_processing_state)
            
            # Update status progressively
            self.root.after(0, lambda: self._update_status("Analyzing question..."))
            
            # Process the query
            response = self.rag_pipeline.process_query(question, class_num)
            
            # Update UI with results
            self.root.after(0, lambda: self._display_response(response, question, class_num))
            
        except Exception as e:
            self.logger.error(f"Error processing question: {e}")
            self.root.after(0, lambda: self._handle_processing_error(e))
        
        finally:
            self.processing = False
            self.root.after(0, self._exit_processing_state)
    
    def _enter_processing_state(self):
        """Enter processing state - disable inputs and show progress."""
        self.ask_button.config(state=tk.DISABLED)
        self.clear_button.config(state=tk.DISABLED)
        self.question_text.config(state=tk.DISABLED)
        self._update_status("Processing your question...")
    
    def _exit_processing_state(self):
        """Exit processing state - re-enable inputs."""
        self.ask_button.config(state=tk.NORMAL)
        self.clear_button.config(state=tk.NORMAL)
        self.question_text.config(state=tk.NORMAL)
        self._update_status("Ready")
    
    def _update_status(self, message: str, style: str = 'Info.TLabel'):
        """Update status bar message."""
        self.status_var.set(message)
        # Note: ttk.Label style changes require recreating the widget in full implementation
    
    def _display_response(self, response: RAGResponse, question: str, class_num: int):
        """Display the RAG response in the GUI."""
        try:
            # Store current response
            self.current_response = response
            
            # Add to conversation history
            conversation_entry = {
                'timestamp': datetime.now().isoformat(),
                'question': question,
                'class': class_num,
                'response': response.to_dict()
            }
            self.conversation_history.append(conversation_entry)
            
            # Clear previous collapsible sections
            for widget in self.collapsible_container.winfo_children():
                widget.destroy()
            
            # Display answer
            self.answer_text.config(state=tk.NORMAL)
            self.answer_text.delete(1.0, tk.END)
            
            # Main answer
            self.answer_text.insert(tk.END, response.answer)
            
            # Add metadata
            metadata_text = f"\n\n" + "─" * 50 + "\n"
            metadata_text += f"Processing Time: {response.metadata.get('processing_time', 0):.3f}s\n"
            metadata_text += f"Documents Retrieved: {response.metadata.get('documents_retrieved', 0)}\n"
            metadata_text += f"Cache Hit: {'Yes' if response.cache_hit else 'No'}\n"
            
            self.answer_text.insert(tk.END, metadata_text)
            self.answer_text.config(state=tk.DISABLED)
            
            # Auto-scroll to top
            self.answer_text.see(1.0)
            
            # Create collapsible sections
            if response.sources:
                self._create_sources_section(response.sources)
            
            # Enable copy button
            self.copy_button.config(state=tk.NORMAL)
            
            # Update status with success message
            self._update_status(f"Answer generated successfully! ({len(response.sources)} sources used)")
            
        except Exception as e:
            self.logger.error(f"Error displaying response: {e}")
            messagebox.showerror("Display Error", f"Error displaying response: {e}")
    
    def _create_sources_section(self, sources: List[Dict[str, Any]]):
        """Create collapsible section for retrieved sources."""
        sources_section = CollapsibleFrame(
            self.collapsible_container,
            f"Retrieved Sources ({len(sources)})",
            '#f8f9fa'
        )
        sources_section.pack(fill=tk.X, pady=(0, 5))
        
        content_frame = sources_section.get_content_frame()
        
        for i, source in enumerate(sources[:5], 1):  # Show top 5 sources
            content = source.get('content', '')
            
            # Source frame
            source_frame = tk.Frame(content_frame, bg='#ffffff', relief=tk.RIDGE, bd=1)
            source_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Header
            header_frame = tk.Frame(source_frame, bg='#f8f9fa')
            header_frame.pack(fill=tk.X, padx=5, pady=2)
            
            source_label = tk.Label(
                header_frame,
                text=f"Source {i}",
                font=('Arial', 10, 'bold'),
                bg='#f8f9fa',
                fg='#2c3e50'
            )
            source_label.pack(side=tk.LEFT)
            
            # Content
            content_label = tk.Label(
                source_frame,
                text=content[:200] + ("..." if len(content) > 200 else ""),
                font=('Arial', 9),
                bg='#ffffff',
                fg='#495057',
                wraplength=800,
                justify=tk.LEFT
            )
            content_label.pack(fill=tk.X, padx=10, pady=5)
    
    def _handle_processing_error(self, error: Exception):
        """Handle errors during question processing."""
        self.logger.error(f"Processing error: {error}")
        
        # Show user-friendly error message
        result = messagebox.askyesno(
            "Processing Error",
            f"An error occurred while processing your question:\n\n{str(error)}\n\n"
            "Would you like to retry?"
        )
        
        if result:
            # Retry the question
            self._on_ask_question()
    
    def _on_clear(self):
        """Handle clear button click."""
        # Clear question input
        self.question_text.config(state=tk.NORMAL)
        self.question_text.delete(1.0, tk.END)
        self._add_placeholder_to_question()
        
        # Clear answer
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete(1.0, tk.END)
        self.answer_text.config(state=tk.DISABLED)
        
        # Clear collapsible sections
        for widget in self.collapsible_container.winfo_children():
            widget.destroy()
        
        # Reset state
        self.current_response = None
        self.copy_button.config(state=tk.DISABLED)
        self._update_status("Ready")
        
        # Focus on question input
        self.question_text.focus()
    
    def _on_copy_answer(self):
        """Copy answer to clipboard."""
        if self.current_response:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(self.current_response.answer)
                self._update_status("Answer copied to clipboard!")
                
                # Reset status after 3 seconds
                self.root.after(3000, lambda: self._update_status("Ready"))
                
            except Exception as e:
                messagebox.showerror("Copy Error", f"Failed to copy to clipboard: {e}")
    
    def _on_export_history(self):
        """Export conversation history to file."""
        if not self.conversation_history:
            messagebox.showinfo("No History", "No conversation history to export.")
            return
        
        try:
            # Ask for file location
            filename = filedialog.asksaveasfilename(
                title="Export Conversation History",
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("JSON files", "*.json"),
                    ("All files", "*.*")
                ]
            )
            
            if filename:
                file_path = Path(filename)
                
                if file_path.suffix.lower() == '.json':
                    # Export as JSON
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
                else:
                    # Export as formatted text
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("NCERT RAG Assistant - Conversation History\n")
                        f.write("=" * 50 + "\n\n")
                        
                        for i, entry in enumerate(self.conversation_history, 1):
                            f.write(f"Conversation {i}\n")
                            f.write("-" * 20 + "\n")
                            f.write(f"Timestamp: {entry['timestamp']}\n")
                            f.write(f"Class: {entry['class']}\n")
                            f.write(f"Question: {entry['question']}\n\n")
                            f.write(f"Answer: {entry['response']['answer']}\n\n")
                            
                            if entry['response']['sources']:
                                f.write("Sources:\n")
                                for j, source in enumerate(entry['response']['sources'], 1):
                                    f.write(f"  {j}. Score: {source.get('similarity_score', 0):.3f}\n")
                                    f.write(f"     Content: {source.get('content', '')[:200]}...\n")
                                f.write("\n")
                            
                            f.write("=" * 50 + "\n\n")
                
                self._update_status(f"History exported to {file_path.name}")
                
                # Reset status after 3 seconds
                self.root.after(3000, lambda: self._update_status("Ready"))
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export history: {e}")
    
    def _on_closing(self):
        """Handle window closing event."""
        try:
            # Stop any ongoing processing
            if self.processing and self.current_thread:
                self.processing = False
                # Note: In a full implementation, you might want to implement
                # a more graceful thread termination mechanism
            
            # Cleanup RAG pipeline
            if self.rag_pipeline:
                if hasattr(self.rag_pipeline, '__exit__'):
                    self.rag_pipeline.__exit__(None, None, None)
            
            # Close the application
            self.root.destroy()
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            self.root.destroy()


def main():
    """Main entry point for the GUI application."""
    try:
        app = NCERTRAGAssistantGUI()
        app.run()
    except Exception as e:
        messagebox.showerror(
            "Application Error",
            f"Failed to start NCERT RAG Assistant:\n\n{str(e)}"
        )


if __name__ == "__main__":
    main()