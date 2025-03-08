// ... existing code ...

// Find the function that handles the calculator form submission
function calculateROI(event) {
    event.preventDefault();
    
    // Get form values
    const loanAmount = parseFloat(document.getElementById('loan-amount').value);
    const currentRate = parseFloat(document.getElementById('current-rate').value);
    const buydownRate = parseFloat(document.getElementById('buydown-rate').value);
    const term = parseInt(document.getElementById('loan-term').value);
    
    // Log form values
    console.log("Form values:", { loanAmount, currentRate, buydownRate, term });
    
    // Make API request
    fetch(`/api/roi/${loanAmount}/${currentRate}/${buydownRate}?term=${term}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log("API Response:", data);
            
            // Update results on the page
            document.getElementById('original-payment').textContent = `$${data.original_payment.toFixed(2)}`;
            document.getElementById('buydown-payment').textContent = `$${data.buydown_payment.toFixed(2)}`;
            document.getElementById('monthly-savings').textContent = `$${data.monthly_savings.toFixed(2)}`;
            document.getElementById('buydown-cost').textContent = `$${data.buydown_cost.toFixed(2)}`;
            document.getElementById('breakeven-months').textContent = `${data.breakeven_months} months`;
            
            // Show results section
            document.getElementById('results-section').style.display = 'block';
            
            // Update chart if it exists
            updateROIChart(data);
        })
        .catch(error => {
            console.error('Error calculating ROI:', error);
            alert('Error calculating ROI. Please try again.');
        });
}

// Add this function to update the chart
function updateROIChart(data) {
    // Check if chart container exists
    const chartContainer = document.getElementById('roi-chart');
    if (!chartContainer) return;
    
    // Clear previous chart if it exists
    chartContainer.innerHTML = '';
    
    // Create new chart
    const ctx = document.createElement('canvas');
    chartContainer.appendChild(ctx);
    
    // Calculate breakeven point in years
    const breakeven = data.buydown_cost / (data.monthly_savings * 12);
    
    // Create data for chart - showing cumulative savings over 10 years
    const labels = [];
    const savings = [];
    const costs = [];
    
    for (let year = 0; year <= 10; year++) {
        labels.push(`Year ${year}`);
        savings.push(data.monthly_savings * 12 * year);
        costs.push(data.buydown_cost);
    }
    
    // Create chart
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Cumulative Savings',
                    data: savings,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    fill: true
                },
                {
                    label: 'Buydown Cost',
                    data: costs,
                    borderColor: 'rgba(255, 99, 132, 1)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Rate Buydown ROI Over Time'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `$${context.raw.toFixed(2)}`;
                        }
                    }
                }
            }
        }
    });
}

// Make sure the form is properly connected to the calculateROI function
document.addEventListener('DOMContentLoaded', function() {
    const calculatorForm = document.getElementById('roi-calculator-form');
    if (calculatorForm) {
        calculatorForm.addEventListener('submit', calculateROI);
    }
});

// ... existing code ...