import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import ReadPage from '@/pages/ReadPage.vue'

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/read' },
  { path: '/read', name: 'read', component: ReadPage, meta: { title: 'Read a plate' } },
  {
    path: '/reads/:id',
    name: 'read-detail',
    component: ReadPage,
    props: true,
    meta: { title: 'Stored read' },
  },
  {
    path: '/jobs',
    name: 'jobs',
    component: () => import('@/pages/JobsPage.vue'),
    meta: { title: 'Jobs' },
  },
  {
    path: '/review',
    name: 'review',
    component: () => import('@/pages/ReviewPage.vue'),
    meta: { title: 'Review queue' },
  },
  {
    path: '/evaluation',
    name: 'evaluation',
    component: () => import('@/pages/EvaluationPage.vue'),
    meta: { title: 'Evaluation' },
  },
  {
    path: '/models',
    name: 'models',
    component: () => import('@/pages/ModelsPage.vue'),
    meta: { title: 'Models' },
  },
  {
    path: '/methods',
    name: 'methods',
    component: () => import('@/pages/MethodsPage.vue'),
    meta: { title: 'Methods' },
  },
  {
    path: '/parity',
    name: 'parity',
    component: () => import('@/pages/ParityPage.vue'),
    meta: { title: 'Browser parity' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { title: 'Not found' },
  },
]

export function makeRouter(history = createWebHistory()) {
  const router = createRouter({
    history,
    routes,
    scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
  })
  router.afterEach((to) => {
    const title = typeof to.meta.title === 'string' ? to.meta.title : 'Console'
    if (typeof document !== 'undefined') document.title = `${title} · DetectionX5`
  })
  return router
}
