function renderQuestionTextWithInlineImages(q) {
    const escapedQuestion = q.q.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const normalizedQuestion = escapedQuestion.replace(/\\/g, '/');
    const imgRegex = /img\[(\d+)\]/g;
    return normalizedQuestion.replace(imgRegex, (match, idx) => {
        if (q.imgs && q.imgs[idx]) {
            return `<img src='/${q.imgs[idx]}' alt='Image ${idx}' />`;
        }
        return match;
    });
}

// Replace direct injection of q.q in renderQuestion()
function renderQuestion() {
    const questionHtml = renderQuestionTextWithInlineImages(q);
    // ... existing code to render the question ...
}