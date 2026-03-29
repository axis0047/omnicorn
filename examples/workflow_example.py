"""
Workflow example demonstrating Omnicorn's orchestration capabilities.

This example shows:
- Defining a workflow with multiple steps
- Using checkpoints for state persistence
- Deferring background activities
"""

from omnicorn import orchestrator, activity, defer_activity, start_workflow


# Define activities (background tasks)
@activity(name="send_email", retries=3)
async def send_email_activity(to: str, subject: str, body: str):
    """Send an email (simulated)."""
    print(f"📧 Sending email to {to}: {subject}")
    # Simulate email sending
    import asyncio
    await asyncio.sleep(1)
    print(f"✅ Email sent to {to}")


@activity(name="process_payment", retries=3)
async def process_payment_activity(user_id: str, amount: float):
    """Process a payment (simulated)."""
    print(f"💳 Processing payment: ${amount} for user {user_id}")
    import asyncio
    await asyncio.sleep(2)
    print(f"✅ Payment processed")


# Define workflow
@orchestrator(name="order_fulfillment")
async def order_fulfillment_workflow(ctx):
    """
    Order fulfillment workflow with multiple steps.
    
    Steps:
    1. init - Process payment
    2. send_confirmation - Send confirmation email
    3. ship_order - Ship the order
    4. send_tracking - Send tracking information
    """
    if ctx.step == "init":
        # Process payment first
        await defer_activity(
            "process_payment",
            user_id=ctx.data["user_id"],
            amount=ctx.data["amount"],
        )
        return ctx.checkpoint("send_confirmation", sleep_ms=1000)

    elif ctx.step == "send_confirmation":
        # Send confirmation email
        await defer_activity(
            "send_email",
            to=ctx.data["email"],
            subject="Order Confirmed",
            body=f"Your order for ${ctx.data['amount']} has been confirmed!",
        )
        return ctx.checkpoint("ship_order", sleep_days=1)  # Ship next day

    elif ctx.step == "ship_order":
        # Simulate shipping
        print(f"📦 Shipping order for {ctx.data['user_id']}")
        return ctx.checkpoint("send_tracking", sleep_ms=5000)

    elif ctx.step == "send_tracking":
        # Send tracking information
        await defer_activity(
            "send_email",
            to=ctx.data["email"],
            subject="Order Shipped",
            body="Your order has been shipped! Tracking: ABC123",
        )
        return ctx.finish()


# Example usage
async def start_order_workflow(user_id: str, email: str, amount: float):
    """Start an order fulfillment workflow."""
    import uuid
    workflow_id = f"order_{uuid.uuid4()}"
    await start_workflow(
        "order_fulfillment",
        workflow_id,
        init_data={"user_id": user_id, "email": email, "amount": amount},
    )
    print(f"🚀 Started workflow: {workflow_id}")
    return workflow_id


if __name__ == "__main__":
    # This would be called from your application
    import asyncio
    asyncio.run(start_order_workflow("user_123", "user@example.com", 99.99))
