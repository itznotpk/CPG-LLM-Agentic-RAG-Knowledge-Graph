"""
CPG (Clinical Practice Guidelines) Parser with Structural Analysis.

This module provides hierarchical parsing of CPG PDF documents:
- Header detection via font size/boldness
- Parent-child chunk relationships
- Table extraction to JSON/Markdown
- Algorithm/flowchart vision analysis
- Metadata extraction (evidence levels, populations, categories)
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

import fitz  # PyMuPDF
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CPGSection:
    """Represents a section/subsection in the CPG document."""
    title: str
    level: int  # 1=main section, 2=subsection, 3=sub-subsection
    start_page: int
    end_page: int
    content: str
    children: List['CPGSection'] = field(default_factory=list)
    parent: Optional['CPGSection'] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CPGChunk:
    """Enhanced chunk with hierarchical metadata."""
    content: str
    index: int
    start_char: int
    end_char: int
    
    # Hierarchical structure
    section_hierarchy: List[str]  # e.g., ["4. TREATMENT", "4.2 Pharmacological Treatment"]
    parent_section: Optional[str] = None
    is_recommendation: bool = False
    
    # Metadata
    evidence_level: Optional[str] = None  # Level I, II, III
    grade: Optional[str] = None  # Grade A, B, C
    target_population: Optional[str] = None  # General, Diabetes, Cardiac Disease, etc.
    category: Optional[str] = None  # Diagnosis, Treatment, Referral, Monitoring
    
    # Content type
    is_table: bool = False
    is_algorithm: bool = False
    table_data: Optional[Dict[str, Any]] = None
    algorithm_description: Optional[str] = None
    
    # Entities extracted
    entities: Dict[str, List[str]] = field(default_factory=dict)
    
    # Source info
    page_numbers: List[int] = field(default_factory=list)
    token_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# HEADER DETECTION PATTERNS
# =============================================================================

# CPG Section Header Patterns
SECTION_PATTERNS = {
    'main_section': re.compile(r'^(\d+)\.\s+([A-Z][A-Z\s&]+)$'),  # "4. TREATMENT"
    'subsection': re.compile(r'^(\d+\.\d+)\s+(.+)$'),  # "4.2 Pharmacological Treatment"
    'sub_subsection': re.compile(r'^(\d+\.\d+\.\d+)\s+(.+)$'),  # "4.2.1 PDE5 Inhibitors"
    'recommendation': re.compile(r'Recommendation\s*(\d+)', re.IGNORECASE),
    'appendix': re.compile(r'^Appendix\s*(\d+|[A-Z])', re.IGNORECASE),
    'algorithm': re.compile(r'Algorithm\s*(\d+|[A-Z])', re.IGNORECASE),
    'table': re.compile(r'Table\s*(\d+|[A-Z])', re.IGNORECASE),
}

# Evidence Level Patterns
EVIDENCE_PATTERNS = {
    'level': re.compile(r'Level\s+([I]+|[1-3])', re.IGNORECASE),
    'grade': re.compile(r'Grade\s+([A-C])', re.IGNORECASE),
    'key_recommendation': re.compile(r'Key\s+Recommendation', re.IGNORECASE),
}

# Target Population Keywords
POPULATION_KEYWORDS = {
    'General': ['general population', 'all patients', 'men with ed'],
    'Diabetes': ['diabetes', 'diabetic', 'dm', 'type 2 diabetes', 'hyperglycemia'],
    'Cardiac Disease': ['cardiac', 'cardiovascular', 'heart disease', 'cvd', 'ihd', 'heart failure'],
    'Spinal Cord Injury': ['spinal cord injury', 'sci', 'neurogenic'],
    'Hypertension': ['hypertension', 'hypertensive', 'high blood pressure'],
    'Elderly': ['elderly', 'older men', 'advanced age', 'geriatric'],
    'Post-prostatectomy': ['prostatectomy', 'radical prostatectomy', 'post-surgical'],
}

# Category Keywords
CATEGORY_KEYWORDS = {
    'Diagnosis': ['diagnosis', 'assessment', 'evaluation', 'history', 'examination', 'investigation'],
    'Treatment': ['treatment', 'therapy', 'management', 'pharmacological', 'intervention'],
    'Referral': ['referral', 'refer', 'specialist', 'urologist', 'cardiologist', 'psychiatrist'],
    'Monitoring': ['monitoring', 'follow-up', 'surveillance', 'review'],
    'Prevention': ['prevention', 'preventive', 'lifestyle modification', 'risk reduction'],
}


# =============================================================================
# CPG PARSER CLASS
# =============================================================================

class CPGParser:
    """
    Parser for Clinical Practice Guidelines PDFs.
    
    Uses PyMuPDF (fitz) to extract structured content with:
    - Font-based header detection
    - Hierarchical section parsing
    - Table extraction to JSON/Markdown
    - Algorithm/flowchart handling via Vision LLM
    """
    
    def __init__(
        self,
        vision_model: Optional[str] = None,
        chunk_size: int = 1200,
        chunk_overlap: int = 200
    ):
        """
        Initialize CPG Parser.
        
        Args:
            vision_model: Model for vision analysis of flowcharts (e.g., 'gemini-2.0-flash')
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
        """
        self.vision_model = vision_model or os.getenv("VISION_MODEL", "google/gemini-2.0-flash-001")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Font size thresholds for header detection (will be calibrated per document)
        self.header_sizes = {
            'title': 18.0,
            'main_section': 14.0,
            'subsection': 12.0,
            'body': 10.0
        }
    
    async def parse_pdf(self, pdf_path: str) -> Tuple[str, List[CPGChunk], Dict[str, Any]]:
        """
        Parse a CPG PDF into structured chunks.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple of (full_content, list of CPGChunks, document_metadata)
        """
        logger.info(f"Parsing CPG PDF: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        
        # Step 1: Analyze document structure (font sizes, headers)
        doc_structure = self._analyze_document_structure(doc)
        
        # Step 2: Extract all text blocks with formatting
        text_blocks = self._extract_text_blocks(doc)
        
        # Step 3: Build section hierarchy
        sections = self._build_section_hierarchy(text_blocks)
        
        # Step 4: Extract tables
        tables = self._extract_tables(doc)
        
        # Step 5: Extract algorithms/flowcharts (images)
        algorithms = await self._extract_algorithms(doc)
        
        # Step 6: Create hierarchical chunks
        chunks = self._create_hierarchical_chunks(sections, tables, algorithms)
        
        # Step 7: Extract document metadata
        doc_metadata = {
            'title': doc_structure.get('title', os.path.basename(pdf_path)),
            'page_count': len(doc),
            'sections': [s.title for s in sections if s.level == 1],
            'table_count': len(tables),
            'algorithm_count': len(algorithms),
            'parse_date': datetime.now().isoformat()
        }
        
        # Get full content for backward compatibility
        full_content = "\n\n".join([c.content for c in chunks])
        
        doc.close()
        
        logger.info(f"Parsed {len(chunks)} chunks, {len(tables)} tables, {len(algorithms)} algorithms")
        
        return full_content, chunks, doc_metadata
    
    def _analyze_document_structure(self, doc: fitz.Document) -> Dict[str, Any]:
        """
        Analyze document to determine font sizes for headers.
        
        Args:
            doc: PyMuPDF document
            
        Returns:
            Document structure analysis
        """
        font_sizes = []
        title_candidates = []
        
        # Sample first few pages to understand font structure
        for page_num in range(min(5, len(doc))):
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            
            for block in blocks:
                if block["type"] == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            size = span.get("size", 10)
                            text = span.get("text", "").strip()
                            flags = span.get("flags", 0)
                            is_bold = bool(flags & 2**4)  # Bold flag
                            
                            font_sizes.append(size)
                            
                            # Title candidates: large font on first pages
                            if page_num < 2 and size > 14 and len(text) > 5:
                                title_candidates.append((text, size))
        
        # Determine font size thresholds
        if font_sizes:
            sizes_sorted = sorted(set(font_sizes), reverse=True)
            if len(sizes_sorted) >= 4:
                self.header_sizes = {
                    'title': sizes_sorted[0],
                    'main_section': sizes_sorted[1],
                    'subsection': sizes_sorted[2],
                    'body': sizes_sorted[3]
                }
        
        # Get document title
        title = ""
        if title_candidates:
            # Pick the largest font text as title
            title = max(title_candidates, key=lambda x: x[1])[0]
        
        return {
            'title': title,
            'header_sizes': self.header_sizes,
            'font_distribution': font_sizes
        }
    
    def _extract_text_blocks(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """
        Extract all text blocks with formatting info.
        
        Args:
            doc: PyMuPDF document
            
        Returns:
            List of text blocks with metadata
        """
        blocks = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            
            for block in page_blocks:
                if block["type"] == 0:  # Text block
                    block_text = ""
                    max_font_size = 0
                    is_bold = False
                    
                    for line in block.get("lines", []):
                        line_text = ""
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")
                            size = span.get("size", 10)
                            if size > max_font_size:
                                max_font_size = size
                            if span.get("flags", 0) & 2**4:
                                is_bold = True
                        block_text += line_text + "\n"
                    
                    block_text = block_text.strip()
                    if block_text:
                        blocks.append({
                            'text': block_text,
                            'page': page_num,
                            'font_size': max_font_size,
                            'is_bold': is_bold,
                            'bbox': block.get('bbox', []),
                            'is_header': self._is_header(block_text, max_font_size, is_bold)
                        })
        
        return blocks
    
    def _is_header(self, text: str, font_size: float, is_bold: bool) -> Optional[int]:
        """
        Determine if text is a header and its level.
        
        Args:
            text: Block text
            font_size: Font size
            is_bold: Whether text is bold
            
        Returns:
            Header level (1-3) or None if not a header
        """
        # Check pattern-based headers first
        for pattern_name, pattern in SECTION_PATTERNS.items():
            if pattern.match(text.strip()):
                if pattern_name in ['main_section', 'appendix']:
                    return 1
                elif pattern_name in ['subsection', 'algorithm', 'table']:
                    return 2
                elif pattern_name == 'sub_subsection':
                    return 3
        
        # Font-size based detection
        if font_size >= self.header_sizes['main_section'] and is_bold:
            return 1
        elif font_size >= self.header_sizes['subsection'] and is_bold:
            return 2
        elif is_bold and len(text.split()) < 10:  # Short bold text
            return 3
        
        return None
    
    def _build_section_hierarchy(self, text_blocks: List[Dict[str, Any]]) -> List[CPGSection]:
        """
        Build hierarchical section structure from text blocks.
        
        Args:
            text_blocks: List of text blocks
            
        Returns:
            List of top-level sections with nested children
        """
        sections = []
        current_sections = {1: None, 2: None, 3: None}
        current_content = []
        
        for block in text_blocks:
            header_level = block['is_header']
            
            if header_level:
                # Save accumulated content to current section
                if current_sections[1] and current_content:
                    # Find the lowest level active section
                    for level in [3, 2, 1]:
                        if current_sections[level]:
                            current_sections[level].content = "\n".join(current_content)
                            break
                    current_content = []
                
                # Create new section
                new_section = CPGSection(
                    title=block['text'].strip(),
                    level=header_level,
                    start_page=block['page'],
                    end_page=block['page'],
                    content="",
                    metadata={
                        'font_size': block['font_size'],
                        'is_bold': block['is_bold']
                    }
                )
                
                # Set parent-child relationships
                if header_level == 1:
                    sections.append(new_section)
                    current_sections = {1: new_section, 2: None, 3: None}
                elif header_level == 2:
                    if current_sections[1]:
                        new_section.parent = current_sections[1]
                        current_sections[1].children.append(new_section)
                    current_sections[2] = new_section
                    current_sections[3] = None
                elif header_level == 3:
                    parent = current_sections[2] or current_sections[1]
                    if parent:
                        new_section.parent = parent
                        parent.children.append(new_section)
                    current_sections[3] = new_section
            else:
                # Accumulate content
                current_content.append(block['text'])
        
        # Save final content
        if current_content:
            for level in [3, 2, 1]:
                if current_sections[level]:
                    current_sections[level].content = "\n".join(current_content)
                    break
        
        return sections
    
    def _extract_tables(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF and convert to structured format.
        
        Args:
            doc: PyMuPDF document
            
        Returns:
            List of table dictionaries
        """
        tables = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Try to find tables using pymupdf's built-in table detection
            try:
                page_tables = page.find_tables()
                
                for idx, table in enumerate(page_tables):
                    # Extract table data
                    table_data = table.extract()
                    
                    if not table_data or len(table_data) < 2:
                        continue
                    
                    # Convert to structured format
                    headers = table_data[0] if table_data else []
                    rows = table_data[1:] if len(table_data) > 1 else []
                    
                    # Clean headers
                    headers = [str(h).strip() if h else f"Column_{i}" for i, h in enumerate(headers)]
                    
                    # Convert to JSON-like structure
                    json_table = []
                    for row in rows:
                        row_dict = {}
                        for i, cell in enumerate(row):
                            if i < len(headers):
                                row_dict[headers[i]] = str(cell).strip() if cell else ""
                        if any(row_dict.values()):
                            json_table.append(row_dict)
                    
                    # Also create markdown version
                    markdown_table = self._table_to_markdown(headers, rows)
                    
                    tables.append({
                        'page': page_num,
                        'index': idx,
                        'headers': headers,
                        'rows': rows,
                        'json': json_table,
                        'markdown': markdown_table,
                        'bbox': table.bbox if hasattr(table, 'bbox') else None
                    })
                    
            except Exception as e:
                logger.warning(f"Table extraction failed on page {page_num}: {e}")
                continue
        
        logger.info(f"Extracted {len(tables)} tables from PDF")
        return tables
    
    def _table_to_markdown(self, headers: List[str], rows: List[List[Any]]) -> str:
        """Convert table data to markdown format."""
        if not headers:
            return ""
        
        lines = []
        
        # Header row
        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        
        # Separator
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        
        # Data rows
        for row in rows:
            cells = [str(c).strip() if c else "" for c in row]
            # Pad if necessary
            while len(cells) < len(headers):
                cells.append("")
            lines.append("| " + " | ".join(cells[:len(headers)]) + " |")
        
        return "\n".join(lines)
    
    async def _extract_algorithms(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """
        Extract algorithm/flowchart images and describe using Vision LLM.
        
        Args:
            doc: PyMuPDF document
            
        Returns:
            List of algorithm descriptions
        """
        algorithms = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            
            for img_idx, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    
                    if not base_image:
                        continue
                    
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Check if image is significant (likely a flowchart)
                    # Flowcharts are usually larger images
                    if len(image_bytes) < 10000:  # Skip small icons
                        continue
                    
                    # Use Vision LLM to describe the flowchart
                    description = await self._describe_algorithm_image(
                        image_bytes, 
                        image_ext,
                        page_num
                    )
                    
                    if description:
                        algorithms.append({
                            'page': page_num,
                            'index': img_idx,
                            'description': description,
                            'image_size': len(image_bytes)
                        })
                        
                except Exception as e:
                    logger.warning(f"Failed to extract image on page {page_num}: {e}")
                    continue
        
        logger.info(f"Extracted and described {len(algorithms)} algorithms/flowcharts")
        return algorithms
    
    async def _describe_algorithm_image(
        self, 
        image_bytes: bytes, 
        image_ext: str,
        page_num: int
    ) -> Optional[str]:
        """
        Use Vision LLM to describe a flowchart/algorithm image.
        
        Args:
            image_bytes: Raw image data
            image_ext: Image extension (png, jpg, etc.)
            page_num: Page number for context
            
        Returns:
            Text description of the algorithm
        """
        try:
            import base64
            from openai import AsyncOpenAI
            
            # Encode image to base64
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            mime_type = f"image/{image_ext}" if image_ext else "image/png"
            
            # Use OpenRouter or Gemini for vision
            client = AsyncOpenAI(
                api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY"),
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            )
            
            prompt = """Analyze this medical flowchart/algorithm from a Clinical Practice Guidelines document.

Convert it to a step-by-step text description that can be used for RAG retrieval. Format as:

Step 1: [Initial assessment/question]
- If [condition A] → [action/next step]
- If [condition B] → [action/next step]

Step 2: [Next decision point]
...

Include all decision points, conditions, and outcomes visible in the flowchart.
Focus on clinical decision-making logic."""

            response = await client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.warning(f"Vision analysis failed for page {page_num}: {e}")
            return None
    
    def _create_hierarchical_chunks(
        self,
        sections: List[CPGSection],
        tables: List[Dict[str, Any]],
        algorithms: List[Dict[str, Any]]
    ) -> List[CPGChunk]:
        """
        Create hierarchical chunks from parsed structure.
        
        Args:
            sections: Hierarchical sections
            tables: Extracted tables
            algorithms: Algorithm descriptions
            
        Returns:
            List of CPGChunks with full metadata
        """
        chunks = []
        chunk_index = 0
        
        # Process sections recursively
        def process_section(section: CPGSection, hierarchy: List[str]):
            nonlocal chunk_index
            
            current_hierarchy = hierarchy + [section.title]
            
            if section.content.strip():
                # Split content if too long
                content_chunks = self._split_content(section.content)
                
                for content in content_chunks:
                    # Extract metadata
                    evidence = self._extract_evidence_level(content)
                    grade = self._extract_grade(content)
                    population = self._extract_population(content)
                    category = self._extract_category(section.title, content)
                    is_recommendation = bool(EVIDENCE_PATTERNS['key_recommendation'].search(content))
                    
                    chunk = CPGChunk(
                        content=content,
                        index=chunk_index,
                        start_char=0,  # Will be calculated later
                        end_char=len(content),
                        section_hierarchy=current_hierarchy,
                        parent_section=hierarchy[-1] if hierarchy else None,
                        is_recommendation=is_recommendation or grade is not None,
                        evidence_level=evidence,
                        grade=grade,
                        target_population=population,
                        category=category,
                        page_numbers=[section.start_page],
                        token_count=len(content) // 4,
                        metadata={
                            'section_title': section.title,
                            'section_level': section.level
                        }
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            
            # Process children
            for child in section.children:
                process_section(child, current_hierarchy)
        
        # Process all top-level sections
        for section in sections:
            process_section(section, [])
        
        # Add table chunks
        for table in tables:
            # Use JSON format for tables (structured, LLM-readable)
            table_content = f"**Table (Page {table['page'] + 1})**\n\n"
            table_content += json.dumps(table['json'], indent=2) if table['json'] else table['markdown']
            
            chunk = CPGChunk(
                content=table_content,
                index=chunk_index,
                start_char=0,
                end_char=len(table_content),
                section_hierarchy=["Tables"],
                is_table=True,
                table_data=table['json'],
                page_numbers=[table['page']],
                token_count=len(table_content) // 4,
                metadata={'table_index': table['index'], 'headers': table['headers']}
            )
            chunks.append(chunk)
            chunk_index += 1
        
        # Add algorithm chunks
        for algo in algorithms:
            algo_content = f"**Algorithm/Flowchart (Page {algo['page'] + 1})**\n\n"
            algo_content += algo['description']
            
            chunk = CPGChunk(
                content=algo_content,
                index=chunk_index,
                start_char=0,
                end_char=len(algo_content),
                section_hierarchy=["Algorithms"],
                is_algorithm=True,
                algorithm_description=algo['description'],
                page_numbers=[algo['page']],
                token_count=len(algo_content) // 4,
                metadata={'algorithm_index': algo['index']}
            )
            chunks.append(chunk)
            chunk_index += 1
        
        return chunks
    
    def _split_content(self, content: str) -> List[str]:
        """Split content into appropriately sized chunks."""
        if len(content) <= self.chunk_size:
            return [content]
        
        chunks = []
        current_chunk = ""
        
        # Split on paragraphs first
        paragraphs = content.split("\n\n")
        
        for para in paragraphs:
            if len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Handle oversized paragraphs
                if len(para) > self.chunk_size:
                    sentences = para.split(". ")
                    current_chunk = ""
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) <= self.chunk_size:
                            current_chunk += (". " if current_chunk else "") + sentence
                        else:
                            if current_chunk:
                                chunks.append(current_chunk + ".")
                            current_chunk = sentence
                else:
                    current_chunk = para
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _extract_evidence_level(self, text: str) -> Optional[str]:
        """Extract evidence level from text."""
        match = EVIDENCE_PATTERNS['level'].search(text)
        if match:
            level = match.group(1)
            # Normalize to roman numerals
            if level == '1':
                return 'Level I'
            elif level == '2':
                return 'Level II'
            elif level == '3':
                return 'Level III'
            return f'Level {level}'
        return None
    
    def _extract_grade(self, text: str) -> Optional[str]:
        """Extract recommendation grade from text."""
        match = EVIDENCE_PATTERNS['grade'].search(text)
        if match:
            return f'Grade {match.group(1).upper()}'
        if EVIDENCE_PATTERNS['key_recommendation'].search(text):
            return 'Key Recommendation'
        return None
    
    def _extract_population(self, text: str) -> Optional[str]:
        """Extract target population from text."""
        text_lower = text.lower()
        for population, keywords in POPULATION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return population
        return 'General'
    
    def _extract_category(self, section_title: str, content: str) -> Optional[str]:
        """Extract category from section title and content."""
        combined = (section_title + " " + content).lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined:
                    return category
        return None


# =============================================================================
# METADATA EXTRACTOR (For use with existing chunks)
# =============================================================================

class CPGMetadataExtractor:
    """
    Extract CPG-specific metadata from text chunks.
    
    Use this to enrich existing chunks with evidence levels,
    population targeting, and categories.
    """
    
    @staticmethod
    def extract_all_metadata(text: str, section_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract all CPG metadata from text.
        
        Args:
            text: Chunk text content
            section_context: Optional parent section title for context
            
        Returns:
            Dictionary of extracted metadata
        """
        combined = f"{section_context or ''} {text}"
        
        return {
            'evidence_level': CPGMetadataExtractor._get_evidence_level(text),
            'grade': CPGMetadataExtractor._get_grade(text),
            'target_population': CPGMetadataExtractor._get_population(combined),
            'category': CPGMetadataExtractor._get_category(combined),
            'is_recommendation': CPGMetadataExtractor._is_recommendation(text),
            'entities_mentioned': CPGMetadataExtractor._count_entities(text)
        }
    
    @staticmethod
    def _get_evidence_level(text: str) -> Optional[str]:
        match = EVIDENCE_PATTERNS['level'].search(text)
        return f"Level {match.group(1)}" if match else None
    
    @staticmethod
    def _get_grade(text: str) -> Optional[str]:
        match = EVIDENCE_PATTERNS['grade'].search(text)
        if match:
            return f"Grade {match.group(1).upper()}"
        if EVIDENCE_PATTERNS['key_recommendation'].search(text):
            return "Key Recommendation"
        return None
    
    @staticmethod
    def _get_population(text: str) -> str:
        text_lower = text.lower()
        for pop, keywords in POPULATION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return pop
        return "General"
    
    @staticmethod
    def _get_category(text: str) -> Optional[str]:
        text_lower = text.lower()
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return cat
        return None
    
    @staticmethod
    def _is_recommendation(text: str) -> bool:
        return bool(
            EVIDENCE_PATTERNS['grade'].search(text) or
            EVIDENCE_PATTERNS['key_recommendation'].search(text) or
            re.search(r'Recommendation\s*\d+', text, re.IGNORECASE) or
            re.search(r'\bshould\b|\bshall\b|\bmust\b|\brecommended\b', text, re.IGNORECASE)
        )
    
    @staticmethod
    def _count_entities(text: str) -> int:
        """Count potential medical entities in text."""
        # Simple heuristic based on capitalized words and medical patterns
        medical_patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # Proper nouns
            r'\bPDE5i?\b|\bSSRI\b|\bECG\b|\bHbA1c\b',  # Abbreviations
            r'\b\d+\s*mg\b|\b\d+\s*ml\b',  # Dosages
        ]
        count = 0
        for pattern in medical_patterns:
            count += len(re.findall(pattern, text))
        return min(count, 50)  # Cap at 50


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_cpg_parser(**kwargs) -> CPGParser:
    """Create a CPG parser with optional configuration."""
    return CPGParser(**kwargs)
