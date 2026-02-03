#!/usr/bin/env python3
"""
Hybrid Search CLI for Loan Products

Combines pgvector (cosine similarity) and pg_search (ParadeDB BM25)
using RRF (Reciprocal Rank Fusion) algorithm.

Uses OpenAI text-embedding-3-small for semantic embeddings.
"""

import os
import sys
from typing import Optional

import click
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Load environment variables
load_dotenv()

console = Console()

# Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
RRF_K = 60  # RRF constant, typically 60


def get_db_connection():
    """Create database connection to Neon PostgreSQL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        console.print("[red]Error: DATABASE_URL not set in environment[/red]")
        sys.exit(1)
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)


def get_openai_client() -> OpenAI:
    """Create OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]Error: OPENAI_API_KEY not set in environment[/red]")
        sys.exit(1)
    return OpenAI(api_key=api_key)


def generate_embedding(client: OpenAI, text: str) -> list[float]:
    """Generate embedding using text-embedding-3-small."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding


def vector_search(conn, embedding: list[float], limit: int = 20) -> list[dict]:
    """
    Perform semantic search using pgvector cosine similarity.
    Returns results with their ranks (1-indexed).
    """
    with conn.cursor() as cur:
        # Convert embedding to PostgreSQL array format
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"

        cur.execute("""
            SELECT
                id,
                name,
                description,
                loan_type,
                min_amount,
                max_amount,
                min_rate,
                max_rate,
                bank_name,
                1 - (embedding <=> %s::vector) as similarity
            FROM loan_products
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (embedding_str, embedding_str, limit))

        results = cur.fetchall()
        # Add rank (1-indexed)
        return [{"rank": i + 1, **dict(row)} for i, row in enumerate(results)]


def bm25_search(conn, query: str, limit: int = 20) -> list[dict]:
    """
    Perform full-text search using ParadeDB BM25.
    Returns results with their ranks (1-indexed).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                id,
                name,
                description,
                loan_type,
                min_amount,
                max_amount,
                min_rate,
                max_rate,
                bank_name,
                paradedb.score(id) as bm25_score
            FROM loan_products
            WHERE id @@@ paradedb.parse(%s)
            ORDER BY paradedb.score(id) DESC
            LIMIT %s
        """, (query, limit))

        results = cur.fetchall()
        return [{"rank": i + 1, **dict(row)} for i, row in enumerate(results)]


def rrf_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = RRF_K,
    vector_weight: float = 1.0,
    bm25_weight: float = 1.0
) -> list[dict]:
    """
    Combine results using Reciprocal Rank Fusion (RRF) algorithm.

    RRF Score = Σ (weight / (k + rank))

    Args:
        vector_results: Results from vector search with ranks
        bm25_results: Results from BM25 search with ranks
        k: RRF constant (default 60)
        vector_weight: Weight for vector search results
        bm25_weight: Weight for BM25 search results

    Returns:
        Combined results sorted by RRF score
    """
    # Dictionary to store RRF scores and document info
    rrf_scores: dict[int, dict] = {}

    # Process vector search results
    for result in vector_results:
        doc_id = result["id"]
        rank = result["rank"]
        rrf_score = vector_weight / (k + rank)

        if doc_id not in rrf_scores:
            rrf_scores[doc_id] = {
                "id": doc_id,
                "name": result["name"],
                "description": result["description"],
                "loan_type": result["loan_type"],
                "min_amount": result.get("min_amount"),
                "max_amount": result.get("max_amount"),
                "min_rate": result.get("min_rate"),
                "max_rate": result.get("max_rate"),
                "bank_name": result.get("bank_name"),
                "rrf_score": 0,
                "vector_rank": rank,
                "vector_similarity": result.get("similarity"),
                "bm25_rank": None,
                "bm25_score": None,
            }
        rrf_scores[doc_id]["rrf_score"] += rrf_score
        rrf_scores[doc_id]["vector_rank"] = rank
        rrf_scores[doc_id]["vector_similarity"] = result.get("similarity")

    # Process BM25 search results
    for result in bm25_results:
        doc_id = result["id"]
        rank = result["rank"]
        rrf_score = bm25_weight / (k + rank)

        if doc_id not in rrf_scores:
            rrf_scores[doc_id] = {
                "id": doc_id,
                "name": result["name"],
                "description": result["description"],
                "loan_type": result["loan_type"],
                "min_amount": result.get("min_amount"),
                "max_amount": result.get("max_amount"),
                "min_rate": result.get("min_rate"),
                "max_rate": result.get("max_rate"),
                "bank_name": result.get("bank_name"),
                "rrf_score": 0,
                "vector_rank": None,
                "vector_similarity": None,
                "bm25_rank": None,
                "bm25_score": None,
            }
        rrf_scores[doc_id]["rrf_score"] += rrf_score
        rrf_scores[doc_id]["bm25_rank"] = rank
        rrf_scores[doc_id]["bm25_score"] = result.get("bm25_score")

    # Sort by RRF score descending
    sorted_results = sorted(
        rrf_scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True
    )

    return sorted_results


def display_results(results: list[dict], show_details: bool = False):
    """Display search results in a formatted table."""
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title="Hybrid Search Results (RRF)", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("상품명", width=25)
    table.add_column("유형", width=12)
    table.add_column("은행", width=15)
    table.add_column("금리", width=12)
    table.add_column("RRF Score", width=10)

    if show_details:
        table.add_column("Vector Rank", width=10)
        table.add_column("BM25 Rank", width=10)

    for i, result in enumerate(results, 1):
        rate_str = ""
        if result.get("min_rate") and result.get("max_rate"):
            rate_str = f"{result['min_rate']:.2f}~{result['max_rate']:.2f}%"

        row = [
            str(i),
            result["name"][:25],
            result["loan_type"][:12] if result["loan_type"] else "-",
            result["bank_name"][:15] if result["bank_name"] else "-",
            rate_str,
            f"{result['rrf_score']:.4f}",
        ]

        if show_details:
            vector_rank = str(result.get("vector_rank", "-"))
            bm25_rank = str(result.get("bm25_rank", "-"))
            row.extend([vector_rank, bm25_rank])

        table.add_row(*row)

    console.print(table)


def display_product_detail(result: dict):
    """Display detailed information about a product."""
    content = Text()
    content.append(f"상품명: ", style="bold")
    content.append(f"{result['name']}\n")
    content.append(f"유형: ", style="bold")
    content.append(f"{result.get('loan_type', 'N/A')}\n")
    content.append(f"은행: ", style="bold")
    content.append(f"{result.get('bank_name', 'N/A')}\n")
    content.append(f"금리: ", style="bold")

    if result.get("min_rate") and result.get("max_rate"):
        content.append(f"{result['min_rate']:.2f}% ~ {result['max_rate']:.2f}%\n")
    else:
        content.append("N/A\n")

    content.append(f"대출한도: ", style="bold")
    if result.get("min_amount") and result.get("max_amount"):
        min_amt = result["min_amount"] / 10000
        max_amt = result["max_amount"] / 10000
        content.append(f"{min_amt:,.0f}만원 ~ {max_amt:,.0f}만원\n")
    else:
        content.append("N/A\n")

    content.append(f"\n설명:\n", style="bold")
    content.append(f"{result.get('description', 'N/A')}\n")

    content.append(f"\n[검색 점수]\n", style="bold yellow")
    content.append(f"RRF Score: {result['rrf_score']:.4f}\n")
    if result.get("vector_rank"):
        content.append(f"Vector Rank: {result['vector_rank']}")
        if result.get("vector_similarity"):
            content.append(f" (similarity: {result['vector_similarity']:.4f})")
        content.append("\n")
    if result.get("bm25_rank"):
        content.append(f"BM25 Rank: {result['bm25_rank']}")
        if result.get("bm25_score"):
            content.append(f" (score: {result['bm25_score']:.4f})")
        content.append("\n")

    console.print(Panel(content, title="상품 상세 정보", border_style="green"))


@click.group()
def cli():
    """Hybrid Search CLI for Loan Products using RRF algorithm."""
    pass


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Maximum number of results to return")
@click.option("--vector-weight", "-vw", default=1.0, help="Weight for vector search (default: 1.0)")
@click.option("--bm25-weight", "-bw", default=1.0, help="Weight for BM25 search (default: 1.0)")
@click.option("--details", "-d", is_flag=True, help="Show ranking details (vector/BM25 ranks)")
@click.option("--show-first", "-f", is_flag=True, help="Show detailed info of first result")
def search(query: str, limit: int, vector_weight: float, bm25_weight: float, details: bool, show_first: bool):
    """
    Perform hybrid search on loan products.

    Combines semantic search (pgvector) and full-text search (pg_search BM25)
    using Reciprocal Rank Fusion (RRF) algorithm.

    Example:
        python cli.py search "청년 전세 대출"
        python cli.py search "저금리 주택담보" --details
        python cli.py search "신용대출" --vector-weight 1.5 --bm25-weight 0.8
    """
    console.print(f"\n[bold blue]Searching for:[/bold blue] {query}\n")

    # Initialize clients
    openai_client = get_openai_client()
    conn = get_db_connection()

    try:
        # Generate embedding for query
        with console.status("[bold green]Generating embedding..."):
            query_embedding = generate_embedding(openai_client, query)

        # Perform vector search
        with console.status("[bold green]Performing vector search..."):
            vector_results = vector_search(conn, query_embedding, limit=limit * 2)
        console.print(f"[dim]Vector search: {len(vector_results)} results[/dim]")

        # Perform BM25 search
        with console.status("[bold green]Performing BM25 search..."):
            bm25_results = bm25_search(conn, query, limit=limit * 2)
        console.print(f"[dim]BM25 search: {len(bm25_results)} results[/dim]")

        # Combine using RRF
        with console.status("[bold green]Applying RRF fusion..."):
            combined_results = rrf_fusion(
                vector_results,
                bm25_results,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight
            )

        # Limit results
        final_results = combined_results[:limit]

        console.print()
        display_results(final_results, show_details=details)

        if show_first and final_results:
            console.print()
            display_product_detail(final_results[0])

    finally:
        conn.close()


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Maximum number of results")
def vector(query: str, limit: int):
    """
    Perform vector-only search (pgvector cosine similarity).

    Example:
        python cli.py vector "주택 구입 자금"
    """
    console.print(f"\n[bold blue]Vector Search for:[/bold blue] {query}\n")

    openai_client = get_openai_client()
    conn = get_db_connection()

    try:
        with console.status("[bold green]Generating embedding..."):
            query_embedding = generate_embedding(openai_client, query)

        with console.status("[bold green]Searching..."):
            results = vector_search(conn, query_embedding, limit=limit)

        table = Table(title="Vector Search Results", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("상품명", width=25)
        table.add_column("유형", width=12)
        table.add_column("은행", width=15)
        table.add_column("Similarity", width=12)

        for i, result in enumerate(results, 1):
            table.add_row(
                str(i),
                result["name"][:25],
                result["loan_type"][:12] if result["loan_type"] else "-",
                result["bank_name"][:15] if result["bank_name"] else "-",
                f"{result.get('similarity', 0):.4f}"
            )

        console.print(table)

    finally:
        conn.close()


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Maximum number of results")
def bm25(query: str, limit: int):
    """
    Perform BM25-only search (ParadeDB pg_search).

    Example:
        python cli.py bm25 "청년 전세"
    """
    console.print(f"\n[bold blue]BM25 Search for:[/bold blue] {query}\n")

    conn = get_db_connection()

    try:
        with console.status("[bold green]Searching..."):
            results = bm25_search(conn, query, limit=limit)

        table = Table(title="BM25 Search Results", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("상품명", width=25)
        table.add_column("유형", width=12)
        table.add_column("은행", width=15)
        table.add_column("BM25 Score", width=12)

        for i, result in enumerate(results, 1):
            table.add_row(
                str(i),
                result["name"][:25],
                result["loan_type"][:12] if result["loan_type"] else "-",
                result["bank_name"][:15] if result["bank_name"] else "-",
                f"{result.get('bm25_score', 0):.4f}"
            )

        console.print(table)

    finally:
        conn.close()


@cli.command()
def init_embeddings():
    """
    Generate embeddings for all loan products that don't have one.

    Combines name, description, loan_type, and eligibility into a single text
    and generates embedding using text-embedding-3-small.
    """
    console.print("\n[bold blue]Initializing embeddings...[/bold blue]\n")

    openai_client = get_openai_client()
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            # Get products without embeddings
            cur.execute("""
                SELECT id, name, description, loan_type, eligibility
                FROM loan_products
                WHERE embedding IS NULL
            """)
            products = cur.fetchall()

        if not products:
            console.print("[green]All products already have embeddings.[/green]")
            return

        console.print(f"Found {len(products)} products without embeddings.\n")

        for product in products:
            # Combine text fields for embedding
            text_parts = [
                product["name"],
                product["description"],
                product["loan_type"] or "",
                product["eligibility"] or ""
            ]
            combined_text = " ".join(filter(None, text_parts))

            with console.status(f"[bold green]Processing: {product['name'][:40]}..."):
                embedding = generate_embedding(openai_client, combined_text)

                # Update database
                embedding_str = "[" + ",".join(map(str, embedding)) + "]"
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE loan_products
                        SET embedding = %s::vector, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (embedding_str, product["id"]))
                conn.commit()

            console.print(f"[green]✓[/green] {product['name']}")

        console.print(f"\n[bold green]Successfully generated {len(products)} embeddings.[/bold green]")

    finally:
        conn.close()


@cli.command()
def list_products():
    """List all loan products in the database."""
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, loan_type, bank_name, min_rate, max_rate,
                       embedding IS NOT NULL as has_embedding
                FROM loan_products
                ORDER BY id
            """)
            products = cur.fetchall()

        table = Table(title="All Loan Products", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim", width=4)
        table.add_column("상품명", width=30)
        table.add_column("유형", width=12)
        table.add_column("은행", width=15)
        table.add_column("금리", width=12)
        table.add_column("Embedding", width=10)

        for product in products:
            rate_str = ""
            if product.get("min_rate") and product.get("max_rate"):
                rate_str = f"{product['min_rate']:.2f}~{product['max_rate']:.2f}%"

            embedding_status = "[green]✓[/green]" if product["has_embedding"] else "[red]✗[/red]"

            table.add_row(
                str(product["id"]),
                product["name"][:30],
                product["loan_type"][:12] if product["loan_type"] else "-",
                product["bank_name"][:15] if product["bank_name"] else "-",
                rate_str,
                embedding_status
            )

        console.print(table)
        console.print(f"\nTotal: {len(products)} products")

    finally:
        conn.close()


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=5, help="Maximum number of results")
def compare(query: str, limit: int):
    """
    Compare results from vector, BM25, and hybrid (RRF) search side by side.

    Useful for understanding how each search method ranks results differently.

    Example:
        python cli.py compare "청년 저금리 전세"
    """
    console.print(f"\n[bold blue]Comparing search methods for:[/bold blue] {query}\n")

    openai_client = get_openai_client()
    conn = get_db_connection()

    try:
        # Generate embedding
        with console.status("[bold green]Generating embedding..."):
            query_embedding = generate_embedding(openai_client, query)

        # Get results from all methods
        vector_results = vector_search(conn, query_embedding, limit=limit)
        bm25_results = bm25_search(conn, query, limit=limit)
        combined_results = rrf_fusion(vector_results, bm25_results)[:limit]

        # Display comparison
        table = Table(title="Search Method Comparison", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Vector Search", width=25)
        table.add_column("BM25 Search", width=25)
        table.add_column("Hybrid (RRF)", width=25)

        for i in range(limit):
            vector_name = vector_results[i]["name"][:25] if i < len(vector_results) else "-"
            bm25_name = bm25_results[i]["name"][:25] if i < len(bm25_results) else "-"
            hybrid_name = combined_results[i]["name"][:25] if i < len(combined_results) else "-"

            table.add_row(str(i + 1), vector_name, bm25_name, hybrid_name)

        console.print(table)

        # Show score details for hybrid results
        console.print("\n[bold]Hybrid (RRF) Score Breakdown:[/bold]")
        for i, result in enumerate(combined_results, 1):
            vector_info = f"V:{result['vector_rank']}" if result.get('vector_rank') else "V:-"
            bm25_info = f"B:{result['bm25_rank']}" if result.get('bm25_rank') else "B:-"
            console.print(f"  {i}. {result['name'][:30]} | RRF: {result['rrf_score']:.4f} | {vector_info} {bm25_info}")

    finally:
        conn.close()


if __name__ == "__main__":
    cli()
