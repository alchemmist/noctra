import React from 'react';
import {createRoot} from 'react-dom/client';
import {ThemeProvider} from '@gravity-ui/uikit';
import '@gravity-ui/uikit/styles/fonts.css';
import '@gravity-ui/uikit/styles/styles.css';
import {App} from './App';
import './index.css';

const container = document.getElementById('root');
if (!container) {
    throw new Error('Root element not found');
}

createRoot(container).render(
    <React.StrictMode>
        <ThemeProvider theme="light">
            <App />
        </ThemeProvider>
    </React.StrictMode>,
);
