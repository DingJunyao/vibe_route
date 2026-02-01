<template>
  <div class="admin-container">
    <el-container>
      <el-header>
        <div class="header-content">
          <el-button @click="$router.back()" :icon="ArrowLeft" class="nav-btn" />
          <el-button @click="$router.push('/home')" :icon="HomeFilled" class="nav-btn home-nav-btn" />
          <h1>后台管理</h1>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-icon><UserIcon /></el-icon>
              <span class="username">{{ authStore.user?.username }}</span>
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="tracks">
                  <el-icon><List /></el-icon>
                  轨迹列表
                </el-dropdown-item>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <el-tabs v-model="activeTab" type="border-card">
          <!-- 系统配置 -->
          <el-tab-pane label="系统配置" name="config">
            <div class="config-tab-content">
              <!-- 加载中显示骨架屏 -->
              <div v-if="loadingConfig" class="config-skeleton">
                <el-skeleton :rows="10" animated />
              </div>
              <!-- 加载完成后显示内容 -->
              <el-card v-else shadow="never">
                <el-form :model="config" label-width="150px" class="config-form">
                <!-- 注册设置 -->
                <div class="form-section">
                  <div class="section-title">注册设置</div>
                  <el-form-item label="允许注册">
                    <el-switch v-model="config.registration_enabled" />
                    <span class="form-tip">是否开放用户注册</span>
                  </el-form-item>
                  <el-form-item label="需要邀请码">
                    <el-switch v-model="config.invite_code_required" />
                    <span class="form-tip">注册时是否需要邀请码</span>
                  </el-form-item>
                </div>

                <!-- 显示设置 -->
                <div class="form-section">
                  <div class="section-title">显示设置</div>
                  <el-form-item label="道路编号显示标牌">
                    <el-switch v-model="config.show_road_sign_in_region_tree" />
                    <span class="form-tip">开启后，经过区域中的道路编号将显示为对应的道路标志 SVG</span>
                  </el-form-item>
                </div>

                <!-- 地图设置 -->
                <div class="form-section">
                  <div class="section-title">地图设置</div>
                  <div class="section-description">
                    <p>选择单选按钮设为默认地图，使用开关启用/禁用地图，<span class="desktop-only">拖拽</span><span class="mobile-only">点击左边的向上 / 向下按钮</span>调整显示顺序。</p>
                    <p>对于高德地图、百度地图、腾讯地图，如果不填 Key，仍然可以使用其点阵图层，但清晰度、更新速度不如矢量图层。</p>
                  </div>
                  <draggable
                    v-model="allMapLayers"
                    item-key="id"
                    handle=".drag-handle"
                    @end="onDragEnd"
                    class="map-layers-list"
                  >
                    <template #item="{ element: layer }">
                      <div
                        class="map-layer-item"
                        :class="{ 'is-default': layer.id === config.default_map_provider }"
                      >
                        <!-- 第一行：拖拽手柄、名称、开关、状态 -->
                        <div class="map-layer-main">
                          <el-icon class="drag-handle desktop-only">
                            <Rank />
                          </el-icon>
                          <!-- 移动端排序按钮 -->
                          <div class="mobile-sort-buttons">
                            <el-button
                              type="primary"
                              :icon="ArrowUp"
                              size="small"
                              text
                              :disabled="isFirstLayer(layer)"
                              @click="moveLayerUp(layer)"
                            />
                            <el-button
                              type="primary"
                              :icon="ArrowDown"
                              size="small"
                              text
                              :disabled="isLastLayer(layer)"
                              @click="moveLayerDown(layer)"
                            />
                          </div>
                          <div class="layer-info">
                            <el-radio
                              :model-value="config.default_map_provider"
                              :value="layer.id"
                              @change="config.default_map_provider = layer.id"
                              :disabled="!layer.enabled"
                            >
                              <span class="layer-name">{{ layer.name }}</span>
                              <span class="layer-id">({{ layer.id }})</span>
                            </el-radio>
                          </div>
                          <el-switch
                            v-model="layer.enabled"
                            @change="onMapLayerToggle(layer)"
                            :disabled="layer.id === config.default_map_provider && layer.enabled"
                          />
                          <span class="layer-status">
                            <template v-if="layer.id === config.default_map_provider">
                              <el-tag size="small" type="success">默认</el-tag>
                            </template>
                            <template v-else-if="layer.enabled">
                              <el-tag size="small" type="info">已启用</el-tag>
                            </template>
                            <template v-else>
                              <el-tag size="small" type="warning">已禁用</el-tag>
                            </template>
                          </span>
                        </div>
                        <!-- 第二行：API 配置输入框 -->
                        <div class="map-layer-config">
                          <!-- 天地图 tk 输入框 -->
                          <el-input
                            v-if="layer.id === 'tianditu'"
                            v-model="layer.tk"
                            placeholder="启用了瓦片服务的浏览器端应用 tk"
                            clearable
                            show-password
                            class="config-input"
                          />
                          <!-- 高德地图 JS API Key 和安全密钥输入框 -->
                          <template v-if="layer.id === 'amap'">
                            <el-input
                              v-model="layer.api_key"
                              placeholder="绑定服务为“Web 端”的 Key（矢量图必填）"
                              clearable
                              show-password
                              class="config-input"
                            />
                            <el-input
                              v-model="layer.security_js_code"
                              placeholder="对应安全密钥（矢量图可选，如有必填）"
                              clearable
                              show-password
                              class="config-input"
                            />
                          </template>
                          <!-- 腾讯地图 API Key 输入框 -->
                          <el-input
                            v-if="layer.id === 'tencent'"
                            v-model="layer.api_key"
                            placeholder="Key（矢量图必填）"
                            clearable
                            show-password
                            class="config-input"
                          />
                          <!-- 百度地图 API Key 输入框 -->
                          <el-input
                            v-if="layer.id === 'baidu'"
                            v-model="layer.api_key"
                            placeholder="浏览器端应用 AK（矢量图必填）"
                            clearable
                            show-password
                            class="config-input"
                          />
                        </div>
                      </div>
                    </template>
                  </draggable>
                </div>

                <!-- 地理编码设置 -->
                <div class="form-section">
                  <div class="section-title">地理编码设置</div>
                  <el-form-item label="编码提供商">
                    <el-radio-group v-model="config.geocoding_provider" @change="onGeocodingProviderChange">
                      <el-radio value="nominatim">Nominatim</el-radio>
                      <el-radio value="gdf">GDF</el-radio>
                      <el-radio value="amap">高德地图</el-radio>
                      <el-radio value="baidu">百度地图</el-radio>
                    </el-radio-group>
                  </el-form-item>

                  <!-- Nominatim 配置 -->
                  <template v-if="config.geocoding_provider === 'nominatim'">
                    <el-form-item label="Nominatim URL">
                      <el-input v-model="config.geocoding_config.nominatim.url" placeholder="http://localhost:8080" />
                      <span class="form-hint">自建 Nominatim 服务的地址</span>
                    </el-form-item>
                  </template>

                  <!-- GDF 配置 -->
                  <template v-if="config.geocoding_provider === 'gdf'">
                    <el-form-item label="数据路径">
                      <el-input v-model="config.geocoding_config.gdf.data_path" placeholder="data/area_data" />
                    </el-form-item>
                  </template>

                  <!-- 高德地图配置 -->
                  <template v-if="config.geocoding_provider === 'amap'">
                    <el-form-item label="API Key">
                      <el-input v-model="config.geocoding_config.amap.api_key" placeholder="绑定服务为“Web 服务”的 Key" show-password />
                    </el-form-item>
                    <el-form-item label="并发频率">
                      <el-input-number v-model="config.geocoding_config.amap.freq" :min="1" :max="50" controls-position="right" />
                      <span class="form-hint">每秒请求数，建议值为 3</span>
                    </el-form-item>
                  </template>

                  <!-- 百度地图配置 -->
                  <template v-if="config.geocoding_provider === 'baidu'">
                    <el-form-item label="API Key">
                      <el-input v-model="config.geocoding_config.baidu.api_key" placeholder="服务端应用 AK" show-password />
                    </el-form-item>
                    <el-form-item label="并发频率">
                      <el-input-number v-model="config.geocoding_config.baidu.freq" :min="1" :max="50" controls-position="right" />
                      <span class="form-hint">每秒请求数，建议值为 3</span>
                    </el-form-item>
                    <el-form-item label="获取英文信息">
                      <el-switch v-model="config.geocoding_config.baidu.get_en_result" />
                      <span class="form-hint">开启后会额外请求英文版本的地理信息</span>
                    </el-form-item>
                  </template>
                </div>

                <!-- 空间计算设置（仅 PostgreSQL 显示） -->
                <div v-if="databaseInfo && databaseInfo.database_type === 'postgresql'" class="form-section">
                  <div class="section-title">空间计算设置</div>
                  <!-- 未启用 PostGIS -->
                  <div v-if="!databaseInfo.postgis_enabled" class="postgis-notice">
                    <el-icon><InfoFilled /></el-icon>
                    <span>启用 PostGIS 可以更高效地处理地理相关数据。请参考相关文档开启。</span>
                  </div>
                  <!-- 已启用 PostGIS -->
                  <template v-else>
                    <el-form-item label="计算后端">
                      <el-radio-group v-model="config.spatial_backend">
                        <el-radio value="auto">自动检测</el-radio>
                        <el-radio value="python">Python (兼容所有数据库)</el-radio>
                        <el-radio value="postgis">PostGIS</el-radio>
                      </el-radio-group>
                      <div class="radio-hint">
                        <template v-if="config.spatial_backend === 'auto'">
                          自动检测数据库能力，PostgreSQL + PostGIS 环境自动使用高性能实现
                        </template>
                        <template v-else-if="config.spatial_backend === 'python'">
                          使用 Python 计算，兼容所有数据库但性能较低
                        </template>
                        <template v-else>
                          使用 PostGIS 空间函数，高性能
                        </template>
                      </div>
                    </el-form-item>
                  </template>
                </div>

                <!-- 道路标志缓存 -->
                <div class="form-section">
                  <div class="section-title">道路标志缓存</div>
                  <el-form-item label="清除缓存">
                    <el-button @click="clearRoadSignCache('way')" :loading="clearingWayCache">
                      清除普通道路缓存
                    </el-button>
                    <el-button @click="clearRoadSignCache('expwy')" :loading="clearingExpwyCache">
                      清除高速公路缓存
                    </el-button>
                    <el-button type="danger" @click="clearRoadSignCache()" :loading="clearingAllCache">
                      清除全部缓存
                    </el-button>
                  </el-form-item>
                </div>

                <el-form-item>
                  <el-button type="primary" @click="saveConfig" :loading="saving">保存配置</el-button>
                  <el-button @click="loadConfig">重置</el-button>
                </el-form-item>
              </el-form>
            </el-card>
            </div>
          </el-tab-pane>

          <!-- 用户管理 -->
          <el-tab-pane label="用户管理" name="users">
            <!-- 搜索、排序、筛选栏 -->
            <el-card shadow="never" class="filter-card">
              <el-row :gutter="12">
                <!-- 搜索 -->
                <el-col :xs="24" :sm="12" :md="8">
                  <el-input
                    v-model="userSearchQuery"
                    placeholder="搜索用户名或邮箱..."
                    :prefix-icon="Search"
                    clearable
                    @input="handleUserSearch"
                  />
                </el-col>
                <!-- 排序 -->
                <el-col :xs="12" :sm="12" :md="8">
                  <div class="sort-buttons">
                    <el-button
                      v-for="item in userSortOptions"
                      :key="item.value"
                      :type="userSortBy === item.value ? 'primary' : ''"
                      @click="handleUserSortClick(item.value)"
                    >
                      {{ item.label }}
                      <el-icon v-if="userSortBy === item.value" class="sort-icon">
                        <component :is="userSortOrder === 'desc' ? ArrowDown : ArrowUp" />
                      </el-icon>
                    </el-button>
                  </div>
                </el-col>
                <!-- 筛选 -->
                <el-col :xs="12" :sm="12" :md="8">
                  <div class="filter-buttons">
                    <el-popover placement="bottom-end" :width="260" trigger="click">
                      <template #reference>
                        <el-button :type="hasActiveFilters ? 'primary' : ''">
                          筛选
                          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                        </el-button>
                      </template>
                      <div class="filter-popover-content">
                        <div class="filter-section">
                          <span class="filter-label">角色：</span>
                          <el-checkbox-group v-model="userRoleFilters" @change="loadUsersImmediate">
                            <el-checkbox-button label="admin">管理员</el-checkbox-button>
                            <el-checkbox-button label="user">普通用户</el-checkbox-button>
                          </el-checkbox-group>
                        </div>
                        <el-divider style="margin: 12px 0" />
                        <div class="filter-section">
                          <span class="filter-label">状态：</span>
                          <el-checkbox-group v-model="userStatusFilters" @change="loadUsersImmediate">
                            <el-checkbox-button label="active">正常</el-checkbox-button>
                            <el-checkbox-button label="inactive">已禁用</el-checkbox-button>
                          </el-checkbox-group>
                        </div>
                        <el-divider style="margin: 12px 0" />
                        <div class="filter-actions">
                          <el-button size="small" style="width: 100%" @click="resetFiltersAndClose">重置筛选</el-button>
                        </div>
                      </div>
                    </el-popover>
                  </div>
                </el-col>
              </el-row>
            </el-card>

            <!-- 加载中显示骨架屏 -->
            <div v-if="loadingUsers" class="list-skeleton">
              <el-skeleton :rows="5" animated />
            </div>

            <!-- 加载完成后显示内容 -->
            <el-card v-else class="list-card" shadow="never">
              <!-- 桌面端表格 -->
              <el-table :data="users" class="pc-table" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="username" label="用户名" min-width="150" />
                <el-table-column prop="email" label="邮箱" min-width="200">
                  <template #default="{ row }">
                    {{ row.email || '-' }}
                  </template>
                </el-table-column>
                <el-table-column label="角色" width="120">
                  <template #default="{ row }">
                    <el-tag :type="row.is_admin ? 'danger' : 'primary'" size="small">
                      {{ row.is_admin ? '管理员' : '普通用户' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                      {{ row.is_active ? '正常' : '已禁用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ formatDateTime(row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="280" fixed="right">
                  <template #default="{ row }">
                    <el-button
                      v-if="!row.is_admin && !isCurrentUser(row) && !isFirstUser(row)"
                      type="primary"
                      size="small"
                      text
                      @click="toggleUserAdmin(row)"
                    >
                      设为管理员
                    </el-button>
                    <el-button
                      v-else
                      type="info"
                      size="small"
                      text
                      :disabled="isCurrentUser(row) || isFirstUser(row)"
                    >
                      {{ row.is_admin ? '已是管理员' : '不可操作' }}
                    </el-button>
                    <el-button
                      v-if="row.is_active && !isCurrentUser(row) && !isFirstUser(row)"
                      type="warning"
                      size="small"
                      text
                      @click="toggleUserActive(row)"
                    >
                      禁用
                    </el-button>
                    <el-button
                      v-else-if="!row.is_active && !isCurrentUser(row) && !isFirstUser(row)"
                      type="success"
                      size="small"
                      text
                      @click="toggleUserActive(row)"
                    >
                      启用
                    </el-button>
                    <el-button
                      v-else
                      type="info"
                      size="small"
                      text
                      disabled
                    >
                      {{ row.is_active ? '不可操作' : '不可操作' }}
                    </el-button>
                    <el-button
                      v-if="!isCurrentUser(row) && !isFirstUser(row)"
                      type="info"
                      size="small"
                      text
                      @click="showResetPasswordDialog(row)"
                    >
                      重置密码
                    </el-button>
                    <el-button
                      v-if="!isCurrentUser(row) && !isFirstUser(row)"
                      type="danger"
                      size="small"
                      text
                      @click="deleteUser(row)"
                    >
                      删除
                    </el-button>
                    <el-button
                      v-else
                      type="info"
                      size="small"
                      text
                      disabled
                    >
                      不可操作
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 移动端卡片列表 -->
              <div class="mobile-card-list">
                <div v-for="user in users" :key="user.id" class="mobile-user-card">
                  <div class="mobile-card-header">
                    <span class="mobile-card-title">{{ user.username }}</span>
                    <div>
                      <el-tag :type="user.is_admin ? 'danger' : 'primary'" size="small">
                        {{ user.is_admin ? '管理员' : '普通用户' }}
                      </el-tag>
                      <el-tag :type="user.is_active ? 'success' : 'info'" size="small" style="margin-left: 4px">
                        {{ user.is_active ? '正常' : '已禁用' }}
                      </el-tag>
                    </div>
                  </div>
                  <div class="mobile-card-body">
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">ID</span>
                      <span class="mobile-card-value">{{ user.id }}</span>
                    </div>
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">邮箱</span>
                      <span class="mobile-card-value">{{ user.email || '-' }}</span>
                    </div>
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">创建时间</span>
                      <span class="mobile-card-value">{{ formatDateTime(user.created_at) }}</span>
                    </div>
                  </div>
                  <div class="mobile-card-actions">
                    <el-button
                      v-if="!user.is_admin && !isCurrentUser(user) && !isFirstUser(user)"
                      type="primary"
                      size="small"
                      @click="toggleUserAdmin(user)"
                    >
                      设为管理员
                    </el-button>
                    <el-button
                      v-if="user.is_active && !isCurrentUser(user) && !isFirstUser(user)"
                      type="warning"
                      size="small"
                      @click="toggleUserActive(user)"
                    >
                      禁用
                    </el-button>
                    <el-button
                      v-else-if="!user.is_active && !isCurrentUser(user) && !isFirstUser(user)"
                      type="success"
                      size="small"
                      @click="toggleUserActive(user)"
                    >
                      启用
                    </el-button>
                    <el-button
                      v-if="!isCurrentUser(user) && !isFirstUser(user)"
                      type="info"
                      size="small"
                      @click="showResetPasswordDialog(user)"
                    >
                      重置密码
                    </el-button>
                    <el-button
                      v-if="!isCurrentUser(user) && !isFirstUser(user)"
                      type="danger"
                      size="small"
                      @click="deleteUser(user)"
                    >
                      删除
                    </el-button>
                    <el-button
                      v-if="isCurrentUser(user) || isFirstUser(user)"
                      type="info"
                      size="small"
                      disabled
                    >
                      不可操作
                    </el-button>
                  </div>
                </div>
              </div>
            </el-card>

            <!-- 分页 -->
            <div class="pagination" v-if="users.length > 0">
              <el-pagination
                v-model:current-page="usersCurrentPage"
                v-model:page-size="usersPageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="usersTotal"
                :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
                @current-change="loadUsers"
                @size-change="loadUsers"
              />
            </div>
          </el-tab-pane>

          <!-- 邀请码管理 -->
          <el-tab-pane label="邀请码" name="invite-codes">
            <!-- 加载中显示骨架屏 -->
            <div v-if="loadingInviteCodes" class="list-skeleton">
              <el-skeleton :rows="5" animated />
            </div>

            <!-- 加载完成后显示内容 -->
            <el-card v-else class="list-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>邀请码列表</span>
                  <el-button type="primary" :icon="Plus" @click="showCreateInviteCodeDialog">
                    创建邀请码
                  </el-button>
                </div>
              </template>

              <!-- 桌面端表格 -->
              <el-table :data="inviteCodes" class="pc-table" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="code" label="邀请码" min-width="150">
                  <template #default="{ row }">
                    <el-tag>{{ row.code }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="使用情况" width="150">
                  <template #default="{ row }">
                    {{ row.used_count }} / {{ row.max_uses }}
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="getInviteCodeStatus(row).type" size="small">
                      {{ getInviteCodeStatus(row).text }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="expires_at" label="过期时间" width="180">
                  <template #default="{ row }">
                    {{ row.expires_at ? formatDateTime(row.expires_at) : '永久有效' }}
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ formatDateTime(row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100" fixed="right">
                  <template #default="{ row }">
                    <el-button
                      v-if="row.is_valid"
                      type="danger"
                      size="small"
                      text
                      @click="deleteInviteCode(row)"
                    >
                      删除
                    </el-button>
                    <el-button v-else type="info" size="small" text disabled>
                      已删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 移动端卡片列表 -->
              <div class="mobile-card-list">
                <div v-for="inviteCode in inviteCodes" :key="inviteCode.id" class="mobile-invite-card">
                  <div class="mobile-card-header">
                    <span class="invite-code-display">{{ inviteCode.code }}</span>
                    <el-tag :type="getInviteCodeStatus(inviteCode).type" size="small">
                      {{ getInviteCodeStatus(inviteCode).text }}
                    </el-tag>
                  </div>
                  <div class="mobile-card-body">
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">使用情况</span>
                      <span class="mobile-card-value">{{ inviteCode.used_count }} / {{ inviteCode.max_uses }}</span>
                    </div>
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">过期时间</span>
                      <span class="mobile-card-value">{{ inviteCode.expires_at ? formatDateTime(inviteCode.expires_at) : '永久有效' }}</span>
                    </div>
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">创建时间</span>
                      <span class="mobile-card-value">{{ formatDateTime(inviteCode.created_at) }}</span>
                    </div>
                  </div>
                  <div class="mobile-card-actions">
                    <el-button
                      v-if="inviteCode.is_valid"
                      type="danger"
                      size="small"
                      @click="deleteInviteCode(inviteCode)"
                    >
                      删除
                    </el-button>
                    <el-button v-else type="info" size="small" disabled>
                      已删除
                    </el-button>
                  </div>
                </div>
              </div>
            </el-card>

            <!-- 分页 -->
            <div class="pagination" v-if="inviteCodes.length > 0">
              <el-pagination
                v-model:current-page="inviteCodesCurrentPage"
                v-model:page-size="inviteCodesPageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="inviteCodesTotal"
                :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
                @current-change="loadInviteCodes"
                @size-change="loadInviteCodes"
              />
            </div>
          </el-tab-pane>

          <!-- 字体管理 -->
          <el-tab-pane label="字体管理" name="fonts">
            <div class="fonts-tab-content">
            <!-- 加载中显示骨架屏 -->
            <div v-if="loadingFonts" class="fonts-skeleton">
              <el-skeleton :rows="8" animated />
            </div>

            <!-- 加载完成后显示内容 -->
            <template v-else>
            <!-- 激活字体选择 -->
            <el-card shadow="never" style="margin-bottom: 16px;">
              <template #header>
                <span>激活字体选择</span>
              </template>
              <el-row :gutter="16">
                <el-col :xs="24" :sm="8">
                  <div class="font-selector-item">
                    <div class="font-selector-label">A 型字体</div>
                    <div class="font-selector-desc">用于中文标题（如"国家高速"、"京"）</div>
                    <el-select
                      :model-value="activeFonts.font_a"
                      @change="(val) => setActiveFont('a', val)"
                      placeholder="选择 A 型字体"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="font in fonts"
                        :key="font.filename"
                        :label="font.filename"
                        :value="font.filename"
                      />
                    </el-select>
                  </div>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <div class="font-selector-item">
                    <div class="font-selector-label">B 型字体</div>
                    <div class="font-selector-desc">用于主数字（如"G5"、"45"）</div>
                    <el-select
                      :model-value="activeFonts.font_b"
                      @change="(val) => setActiveFont('b', val)"
                      placeholder="选择 B 型字体"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="font in fonts"
                        :key="font.filename"
                        :label="font.filename"
                        :value="font.filename"
                      />
                    </el-select>
                  </div>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <div class="font-selector-item">
                    <div class="font-selector-label">C 型字体</div>
                    <div class="font-selector-desc">用于小数字（如"01"）</div>
                    <el-select
                      :model-value="activeFonts.font_c"
                      @change="(val) => setActiveFont('c', val)"
                      placeholder="选择 C 型字体"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="font in fonts"
                        :key="font.filename"
                        :label="font.filename"
                        :value="font.filename"
                      />
                    </el-select>
                  </div>
                </el-col>
              </el-row>
              <el-alert
                v-if="!activeFonts.font_a || !activeFonts.font_b || !activeFonts.font_c"
                type="warning"
                :closable="false"
                style="margin-top: 12px;"
              >
                字体未完整配置，道路标志生成功能将被禁用
              </el-alert>
            </el-card>
            </template>

            <!-- 字体文件列表 -->
            <el-card shadow="never">
              <template #header>
                <div class="card-header">
                  <span>字体文件列表</span>
                  <el-upload
                    :auto-upload="false"
                    :show-file-list="false"
                    :on-change="handleFontUpload"
                    accept=".ttf,.otf,.ttc"
                  >
                    <el-button type="primary" :icon="Plus">上传字体</el-button>
                  </el-upload>
                </div>
              </template>

              <!-- 桌面端表格 -->
              <el-table :data="fonts" class="pc-table" style="width: 100%">
                <el-table-column prop="filename" label="文件名" min-width="200" />
                <el-table-column label="大小" width="120">
                  <template #default="{ row }">
                    {{ formatFileSize(row.size) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="150" fixed="right">
                  <template #default="{ row }">
                    <el-button
                      type="danger"
                      size="small"
                      text
                      @click="deleteFont(row)"
                    >
                      删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 移动端卡片列表 -->
              <div class="mobile-card-list">
                <div v-for="font in fonts" :key="font.filename" class="mobile-font-card">
                  <div class="mobile-card-header">
                    <span class="mobile-card-title">{{ font.filename }}</span>
                  </div>
                  <div class="mobile-card-body">
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">大小</span>
                      <span class="mobile-card-value">{{ formatFileSize(font.size) }}</span>
                    </div>
                  </div>
                  <div class="mobile-card-actions">
                    <el-button
                      type="danger"
                      size="small"
                      @click="deleteFont(font)"
                    >
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
            </el-card>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-main>
    </el-container>

    <!-- 创建邀请码对话框 -->
    <el-dialog v-model="createInviteCodeDialogVisible" title="创建邀请码" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form :model="inviteCodeForm" label-width="120px" class="dialog-form">
        <el-form-item label="邀请码">
          <el-input v-model="inviteCodeForm.code" placeholder="留空自动生成" />
          <span class="form-tip">留空则自动生成随机邀请码</span>
        </el-form-item>
        <el-form-item label="最大使用次数">
          <el-input-number v-model="inviteCodeForm.max_uses" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="有效期（天）">
          <el-input-number v-model="inviteCodeForm.expires_in_days" :min="1" :max="365" />
          <span class="form-tip">留空则永久有效</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createInviteCodeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingInviteCode" @click="createInviteCode">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetPasswordDialogVisible" title="重置密码" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form :model="resetPasswordForm" label-width="100px" class="dialog-form">
        <el-form-item label="用户名">
          <el-input :value="resetPasswordForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="resetPasswordForm.new_password"
            type="password"
            placeholder="请输入新密码（至少 6 位）"
            show-password
            clearable
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="resetPasswordForm.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            show-password
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resettingPassword" @click="confirmResetPassword">
          确认重置
        </el-button>
      </template>
    </el-dialog>

    <!-- 未保存更改确认对话框 -->
    <el-dialog v-model="unsavedChangesDialogVisible" title="提示" :width="isMobile ? '90%' : '420px'" class="unsaved-changes-dialog">
      <p>系统配置有未保存的更改，确定要离开吗？</p>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleUnsavedChanges('cancel')">取消</el-button>
          <el-button type="primary" @click="handleUnsavedChanges('save')">保存配置</el-button>
          <el-button type="danger" @click="handleUnsavedChanges('leave')">离开</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, onUnmounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, HomeFilled, User as UserIcon, ArrowDown, SwitchButton, List, Plus, Rank, ArrowUp, Search, InfoFilled } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import { adminApi, type SystemConfig, type User, type InviteCode, type MapLayerConfig, type CRSType, type FontInfo, type FontConfig, type DatabaseInfo } from '@/api/admin'
import { roadSignApi } from '@/api/roadSign'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/format'
import { useConfigStore } from '@/stores/config'
import { hashPassword } from '@/utils/crypto'

const router = useRouter()
const authStore = useAuthStore()
const configStore = useConfigStore()

// 检查管理员权限
if (!authStore.user?.is_admin) {
  ElMessage.error('需要管理员权限')
  router.push('/')
}

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value <= 1366)

// 监听窗口大小变化
function handleResize() {
  screenWidth.value = window.innerWidth
}

const activeTab = ref('config')
const loadingConfig = ref(false)
const loadingUsers = ref(false)
const loadingInviteCodes = ref(false)
const loadingFonts = ref(false)
const saving = ref(false)
const creatingInviteCode = ref(false)
const uploadingFont = ref(false)

// 标记组件是否已挂载，用于避免卸载后更新状态
const isMounted = ref(true)

// 道路标志缓存清除状态
const clearingWayCache = ref(false)
const clearingExpwyCache = ref(false)
const clearingAllCache = ref(false)

// 用户管理分页
const usersTotal = ref(0)
const usersCurrentPage = ref(1)
const usersPageSize = ref(20)

// 邀请码管理分页
const inviteCodesTotal = ref(0)
const inviteCodesCurrentPage = ref(1)
const inviteCodesPageSize = ref(20)

// 用户搜索、排序、筛选
const userSearchQuery = ref('')
const adminCount = ref(0)  // 管理员数量统计
const userSortBy = ref('created_at')
const userSortOrder = ref<'asc' | 'desc'>('desc')  // 默认降序（最新在前）
const userSortOptions = [
  { label: '创建时间', value: 'created_at' },
  { label: '用户名', value: 'username' },
  { label: '邮箱', value: 'email' },
]
const userRoleFilters = ref<string[]>(['admin', 'user'])  // 默认全选
const userStatusFilters = ref<string[]>(['active'])  // 默认正常状态

// 重置密码
const resetPasswordDialogVisible = ref(false)
const resettingPassword = ref(false)
const resetPasswordForm = reactive({
  user_id: 0,
  username: '',
  new_password: '',
  confirm_password: '',
})

// 未保存更改对话框
const unsavedChangesDialogVisible = ref(false)
let unsavedChangesResolve: ((action: 'save' | 'leave' | 'cancel') => void) | null = null

// 显示未保存更改对话框，返回用户选择的操作
function showUnsavedChangesDialog(): Promise<'save' | 'leave' | 'cancel'> {
  return new Promise((resolve) => {
    unsavedChangesResolve = resolve
    unsavedChangesDialogVisible.value = true
  })
}

// 处理用户选择
function handleUnsavedChanges(action: 'save' | 'leave' | 'cancel') {
  unsavedChangesDialogVisible.value = false
  if (unsavedChangesResolve) {
    unsavedChangesResolve(action)
    unsavedChangesResolve = null
  }
}

// 系统配置
const config = reactive<SystemConfig>({
  registration_enabled: true,
  invite_code_required: false,
  show_road_sign_in_region_tree: true,
  default_map_provider: 'osm',
  geocoding_provider: 'nominatim',
  geocoding_config: {
    nominatim: { url: '', email: '' },
    gdf: { data_path: '' },
    amap: { api_key: '', freq: 3 },
    baidu: { api_key: '', freq: 3, get_en_result: false },
  },
  map_layers: {},
  spatial_backend: 'auto',
})

// 所有地图层列表（按固定顺序）
const allMapLayers = ref<MapLayerConfig[]>([])

// 原始配置（用于检测未保存的更改）
const originalConfig = ref<SystemConfig | null>(null)

// 数据库信息（用于判断是否显示 PostGIS 设置）
const databaseInfo = ref<DatabaseInfo | null>(null)

// 用户列表
const users = ref<User[]>([])

// 邀请码列表
const inviteCodes = ref<InviteCode[]>([])
const createInviteCodeDialogVisible = ref(false)
const inviteCodeForm = reactive({
  code: '',
  max_uses: 1,
  expires_in_days: undefined as number | undefined,
})

// 字体列表
const fonts = ref<FontInfo[]>([])
const activeFonts = ref<FontConfig>({ font_a: undefined, font_b: undefined, font_c: undefined })

// 检测系统配置是否有未保存的更改
function hasUnsavedConfigChanges(): boolean {
  if (!originalConfig.value) return false
  // 比较当前配置和原始配置
  const currentConfig = JSON.parse(JSON.stringify(config))
  return JSON.stringify(currentConfig) !== JSON.stringify(originalConfig.value)
}

// 初始化 geocoding_config
function initGeocodingConfig() {
  if (!config.geocoding_config) {
    config.geocoding_config = {}
  }
  if (!config.geocoding_config.nominatim) {
    config.geocoding_config.nominatim = { url: 'http://localhost:8080' }
  }
  if (!config.geocoding_config.gdf) {
    config.geocoding_config.gdf = { data_path: '' }
  }
  if (!config.geocoding_config.amap) {
    config.geocoding_config.amap = { api_key: '', freq: 3 }
  }
  if (!config.geocoding_config.baidu) {
    config.geocoding_config.baidu = { api_key: '', freq: 3, get_en_result: false }
  }
}

// 加载系统配置
async function loadConfig() {
  loadingConfig.value = true
  try {
    const data = await adminApi.getConfig()
    if (!isMounted.value) return
    Object.assign(config, data)
    initGeocodingConfig()
    // 初始化地图层列表（按固定顺序）
    initMapLayers()
    // 保存原始配置（深拷贝），用于检测未保存的更改
    originalConfig.value = JSON.parse(JSON.stringify(config))
    // 获取数据库信息（用于判断是否显示 PostGIS 设置）
    const dbInfo = await adminApi.getDatabaseInfo()
    if (isMounted.value) {
      databaseInfo.value = dbInfo
    }
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingConfig.value = false
    }
  }
}

// 清除道路标志缓存
async function clearRoadSignCache(signType?: 'way' | 'expwy') {
  // 确认操作
  const typeText = signType === 'way' ? '普通道路' : signType === 'expwy' ? '高速公路' : '全部'
  try {
    await ElMessageBox.confirm(
      `确定要清除${typeText}的道路标志缓存吗？这将删除所有已生成的标志文件。`,
      '确认清除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return // 用户取消
  }

  // 设置对应的加载状态
  if (signType === 'way') {
    clearingWayCache.value = true
  } else if (signType === 'expwy') {
    clearingExpwyCache.value = true
  } else {
    clearingAllCache.value = true
  }

  try {
    const result = await roadSignApi.clearCache(signType)
    ElMessage.success(`已清除 ${result.count} 个缓存`)
  } finally {
    // 重置加载状态
    clearingWayCache.value = false
    clearingExpwyCache.value = false
    clearingAllCache.value = false
  }
}

// 初始化地图层列表
function initMapLayers() {
  if (!config.map_layers) {
    config.map_layers = {}
  }
  // 按 order 字段排序
  allMapLayers.value = Object.values(config.map_layers).sort((a: unknown, b: unknown) => (a as MapLayerConfig).order - (b as MapLayerConfig).order)
}

// 拖拽结束后的处理
function onDragEnd() {
  // 更新所有地图层的 order 值
  allMapLayers.value.forEach((layer: MapLayerConfig, index: number) => {
    layer.order = index
  })
}

// 判断是否为第一个地图层
function isFirstLayer(layer: MapLayerConfig): boolean {
  return allMapLayers.value[0]?.id === layer.id
}

// 判断是否为最后一个地图层
function isLastLayer(layer: MapLayerConfig): boolean {
  return allMapLayers.value[allMapLayers.value.length - 1]?.id === layer.id
}

// 上移地图层
function moveLayerUp(layer: MapLayerConfig) {
  const index = allMapLayers.value.findIndex((l: MapLayerConfig) => l.id === layer.id)
  if (index > 0) {
    // 交换位置
    const temp = allMapLayers.value[index - 1]
    allMapLayers.value[index - 1] = allMapLayers.value[index]
    allMapLayers.value[index] = temp
    // 更新 order 值
    allMapLayers.value.forEach((l: MapLayerConfig, i: number) => {
      l.order = i
    })
  }
}

// 下移地图层
function moveLayerDown(layer: MapLayerConfig) {
  const index = allMapLayers.value.findIndex((l: MapLayerConfig) => l.id === layer.id)
  if (index < allMapLayers.value.length - 1) {
    // 交换位置
    const temp = allMapLayers.value[index + 1]
    allMapLayers.value[index + 1] = allMapLayers.value[index]
    allMapLayers.value[index] = temp
    // 更新 order 值
    allMapLayers.value.forEach((l: MapLayerConfig, i: number) => {
      l.order = i
    })
  }
}

// 地图层切换事件
function onMapLayerToggle(layer: MapLayerConfig) {
  if (!layer.enabled) {
    // 如果禁用的是当前默认地图，需要切换默认地图
    if (layer.id === config.default_map_provider) {
      // 找到第一个启用的地图作为默认
      const firstEnabled = allMapLayers.value.find((l: MapLayerConfig) => l.enabled && l.id !== layer.id)
      if (firstEnabled) {
        config.default_map_provider = firstEnabled.id
      } else {
        // 如果没有其他启用的地图，不允许禁用
        layer.enabled = true
        ElMessage.warning('至少需要保留一个启用的地图')
      }
    }
  }
}

// 保存系统配置
async function saveConfig() {
  saving.value = true
  try {
    // 确保 map_layers 被正确保存
    const updateData: Partial<SystemConfig> = {
      ...config,
      map_layers: config.map_layers,
    }
    // 使用 configStore 的 updateConfig 方法，确保 publicConfig 也被更新
    await configStore.updateConfig(updateData)
    ElMessage.success('配置保存成功')
    // 保存成功后更新原始配置
    originalConfig.value = JSON.parse(JSON.stringify(config))
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
  }
}

// 地理编码提供商切换时初始化配置
function onGeocodingProviderChange() {
  initGeocodingConfig()
}

// 加载用户列表
async function loadUsers() {
  loadingUsers.value = true
  try {
    const response = await adminApi.getUsers({
      page: usersCurrentPage.value,
      page_size: usersPageSize.value,
      search: userSearchQuery.value || undefined,
      sort_by: userSortBy.value,
      sort_order: userSortOrder.value,
      roles: userRoleFilters.value.length === 2 ? undefined : userRoleFilters.value,
      statuses: userStatusFilters.value.length === 2 ? undefined : userStatusFilters.value,
    })
    if (!isMounted.value) return
    users.value = response.items
    usersTotal.value = response.total
    // 统计管理员数量
    adminCount.value = response.items.filter((u: User) => u.is_admin).length
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingUsers.value = false
    }
  }
}

// 立即加载用户（用于筛选，无需防抖）
function loadUsersImmediate() {
  usersCurrentPage.value = 1  // 筛选时重置到第一页
  loadUsers()
}

// 判断是否有激活的筛选条件
const hasActiveFilters = computed(() => {
  const roleFilterActive = userRoleFilters.value.length !== 2
  const statusFilterActive = userStatusFilters.value.length !== 1 || userStatusFilters.value[0] !== 'active'
  return roleFilterActive || statusFilterActive
})

// 用户搜索防抖
let userSearchTimeout: ReturnType<typeof setTimeout> | null = null
function handleUserSearch() {
  if (userSearchTimeout) {
    clearTimeout(userSearchTimeout)
  }
  userSearchTimeout = setTimeout(() => {
    usersCurrentPage.value = 1  // 搜索时重置到第一页
    loadUsers()
  }, 500)
}

// 用户排序点击
function handleUserSortClick(value: string) {
  if (userSortBy.value === value) {
    // 点击当前排序字段，切换排序方向
    userSortOrder.value = userSortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    // 切换到新的排序字段
    userSortBy.value = value
    // 对于创建时间和用户名，使用 desc（倒序，最新/字母序）
    // 对于邮箱，使用 asc（正序，字母序）
    userSortOrder.value = value === 'email' ? 'asc' : 'desc'
  }
  loadUsers()
}

// 重置筛选
function resetFilters() {
  userRoleFilters.value = ['admin', 'user']
  userStatusFilters.value = ['active']
  loadUsersImmediate()
}

// 重置筛选并关闭 popover（需要手动触发 DOM 事件）
function resetFiltersAndClose() {
  resetFilters()
  // 点击页面其他地方来关闭 popover
  document.dispatchEvent(new MouseEvent('click'))
}

// 判断是否为当前用户
function isCurrentUser(user: User): boolean {
  return authStore.user?.id === user.id
}

// 判断是否为第一位用户（ID 最小的用户）
function isFirstUser(user: User): boolean {
  if (users.value.length === 0) return false
  const firstUser = users.value.reduce((min: User | null, u: User) =>
    !min || u.id < min.id ? u : min
  , null)
  return firstUser?.id === user.id
}

// 切换用户管理员状态
async function toggleUserAdmin(user: User) {
  // 检查：如果要取消管理员身份，确保至少还有一位管理员
  if (user.is_admin && adminCount.value <= 1) {
    ElMessage.warning('系统至少需要保留一位管理员')
    return
  }
  try {
    await adminApi.updateUser(user.id, { is_admin: !user.is_admin })
    ElMessage.success('操作成功')
    await loadUsers()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 切换用户启用状态
async function toggleUserActive(user: User) {
  const action = user.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}用户 "${user.username}" 吗？`, '确认操作', {
      type: 'warning',
    })
    await adminApi.updateUser(user.id, { is_active: !user.is_active })
    ElMessage.success('操作成功')
    await loadUsers()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 删除用户
async function deleteUser(user: User) {
  try {
    await ElMessageBox.confirm(`确定要删除用户 "${user.username}" 吗？此操作不可撤销。`, '确认删除', {
      type: 'warning',
    })
    await adminApi.deleteUser(user.id)
    ElMessage.success('删除成功')
    await loadUsers()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 显示重置密码对话框
function showResetPasswordDialog(user: User) {
  resetPasswordForm.user_id = user.id
  resetPasswordForm.username = user.username
  resetPasswordForm.new_password = ''
  resetPasswordForm.confirm_password = ''
  resetPasswordDialogVisible.value = true
}

// 确认重置密码
async function confirmResetPassword() {
  // 验证密码
  if (!resetPasswordForm.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (resetPasswordForm.new_password.length < 6) {
    ElMessage.warning('密码长度至少为 6 位')
    return
  }
  if (resetPasswordForm.new_password !== resetPasswordForm.confirm_password) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  resettingPassword.value = true
  try {
    // 前端先对密码进行 SHA256 加密，与登录流程保持一致
    const hashedPassword = await hashPassword(resetPasswordForm.new_password)
    await adminApi.resetPassword(resetPasswordForm.user_id, hashedPassword)
    ElMessage.success('密码重置成功')
    resetPasswordDialogVisible.value = false
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    resettingPassword.value = false
  }
}

// 加载邀请码列表
async function loadInviteCodes() {
  loadingInviteCodes.value = true
  try {
    const response = await adminApi.getInviteCodes({
      page: inviteCodesCurrentPage.value,
      page_size: inviteCodesPageSize.value,
    })
    if (!isMounted.value) return
    inviteCodes.value = response.items
    inviteCodesTotal.value = response.total
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingInviteCodes.value = false
    }
  }
}

// 显示创建邀请码对话框
function showCreateInviteCodeDialog() {
  inviteCodeForm.code = ''
  inviteCodeForm.max_uses = 1
  inviteCodeForm.expires_in_days = undefined
  createInviteCodeDialogVisible.value = true
}

// 创建邀请码
async function createInviteCode() {
  creatingInviteCode.value = true
  try {
    await adminApi.createInviteCode({
      code: inviteCodeForm.code || undefined,
      max_uses: inviteCodeForm.max_uses,
      expires_in_days: inviteCodeForm.expires_in_days,
    })
    ElMessage.success('邀请码创建成功')
    createInviteCodeDialogVisible.value = false
    await loadInviteCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    creatingInviteCode.value = false
  }
}

// 删除邀请码
async function deleteInviteCode(inviteCode: InviteCode) {
  try {
    await ElMessageBox.confirm(`确定要删除邀请码 "${inviteCode.code}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await adminApi.deleteInviteCode(inviteCode.id)
    ElMessage.success('删除成功')
    await loadInviteCodes()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 获取邀请码状态
function getInviteCodeStatus(inviteCode: InviteCode) {
  if (!inviteCode.is_valid) {
    return { type: 'info', text: '已删除' }
  }
  if (inviteCode.expires_at && new Date(inviteCode.expires_at) < new Date()) {
    return { type: 'danger', text: '已过期' }
  }
  if (inviteCode.used_count >= inviteCode.max_uses) {
    return { type: 'warning', text: '已用完' }
  }
  return { type: 'success', text: '可用' }
}

// 处理用户下拉菜单命令
function handleCommand(command: string) {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      authStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    })
  } else if (command === 'tracks') {
    router.push('/tracks')
  }
}

// 格式化文件大小
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// ========== 字体管理 ==========

// 加载字体列表
async function loadFonts() {
  loadingFonts.value = true
  try {
    const response = await adminApi.getFonts()
    if (!isMounted.value) return
    fonts.value = response.fonts
    activeFonts.value = response.active_fonts
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingFonts.value = false
    }
  }
}

// 设置激活字体
async function setActiveFont(fontType: 'a' | 'b' | 'c', filename: string) {
  try {
    await adminApi.setActiveFont(fontType, filename)
    activeFonts.value[`font_${fontType}`] = filename
    // 刷新配置，使主页能及时更新按钮显示状态
    await configStore.refreshConfig()
    ElMessage.success('字体设置成功')
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 处理字体上传
async function handleFontUpload(file: any) {
  const rawFile = file.raw
  if (!rawFile) return

  uploadingFont.value = true
  try {
    await adminApi.uploadFont(rawFile)
    ElMessage.success('字体上传成功')
    await loadFonts()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    uploadingFont.value = false
  }
}

// 删除字体
async function deleteFont(font: FontInfo) {
  try {
    await ElMessageBox.confirm(`确定要删除字体 "${font.filename}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await adminApi.deleteFont(font.filename)
    ElMessage.success('删除成功')
    await loadFonts()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 监听 tab 切换，如果有未保存的配置更改则提示
watch(activeTab, async (newTab, oldTab) => {
  if (oldTab === 'config' && hasUnsavedConfigChanges()) {
    const action = await showUnsavedChangesDialog()
    if (action === 'leave') {
      // 点击"离开"按钮，重置为原始配置
      if (originalConfig.value) {
        Object.assign(config, originalConfig.value)
        initGeocodingConfig()
        initMapLayers()
      }
    } else if (action === 'save') {
      // 点击"保存配置"按钮
      await saveConfig()
    } else {
      // 点击"取消"按钮，切回原来的 tab
      activeTab.value = oldTab
    }
  }
})

// 路由离开守卫
onBeforeRouteLeave(async (to, from, next) => {
  // 只有在系统配置 tab 且有未保存更改时才提示
  if (activeTab.value === 'config' && hasUnsavedConfigChanges()) {
    const action = await showUnsavedChangesDialog()
    if (action === 'leave') {
      next()
    } else if (action === 'save') {
      await saveConfig()
      next()
    } else {
      next(false)
    }
  } else {
    next()
  }
})

// 浏览器刷新/关闭提示
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (activeTab.value === 'config' && hasUnsavedConfigChanges()) {
    e.preventDefault()
    e.returnValue = '' // Chrome 需要设置 returnValue
    return ''
  }
}

onMounted(async () => {
  await loadConfig()
  await loadUsers()
  await loadInviteCodes()
  await loadFonts()

  // 添加窗口大小监听
  window.addEventListener('resize', handleResize)
  // 添加浏览器刷新/关闭提示
  window.addEventListener('beforeunload', handleBeforeUnload)
})

// 组件即将卸载时设置标志
onBeforeUnmount(() => {
  isMounted.value = false
})

// 组件卸载时移除监听器
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style scoped>
.admin-container {
  height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
}

.admin-container > .el-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  width: 100%;
}

.el-header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  z-index: 100;
  width: 100%;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}

.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
}

.header-content h1 {
  font-size: 20px;
  margin: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  padding: 5px 10px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.user-info .username {
  display: inline;
}

.main {
  flex: 1;
  min-height: 0;
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* 标签页容器固定高度 */
.main > .el-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  overflow-x: hidden;
  width: 100%;
}

.main :deep(.el-tabs__header) {
  flex-shrink: 0;
  overflow: hidden;
}

.main :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  overflow-x: hidden;
}

.main :deep(.el-tab-pane) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overflow-x: hidden;
}

/* 系统配置 tab 可滚动 */
.config-tab-content {
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
}

/* 字体管理 tab 可滚动 */
.fonts-tab-content {
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
}

/* 列表卡片固定高度，内部滚动 */
.list-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overflow-x: hidden;
}

.list-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
}

/* 用户筛选卡片 */
.filter-card {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.filter-card :deep(.el-card__body) {
  padding: 12px;
}

.sort-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.sort-buttons .el-button {
  flex-shrink: 0;
}

.sort-icon {
  margin-left: 4px;
}

.filter-buttons {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.filter-label {
  margin-right: 12px;
  font-weight: 500;
  color: #606266;
}

:deep(.el-checkbox-button) {
  margin-right: 8px;
}

:deep(.el-dropdown-menu__item) {
  padding: 8px 12px;
}

:deep(.el-dropdown-menu) {
  min-width: 200px;
}

/* Popover 筛选样式 */
.filter-popover-content {
  padding: 8px 0;
}

.filter-section {
  padding: 4px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-section .filter-label {
  font-weight: 500;
  color: #606266;
  font-size: 14px;
}

.filter-section .el-checkbox-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-actions {
  padding: 4px 12px;
}

/* PC 端表格样式 */
.pc-table {
  width: 100%;
}

/* 分页器样式 */
.pagination {
  flex-shrink: 0;
  padding: 12px 0;
  display: flex;
  justify-content: center;
  overflow: hidden;
}

.pagination :deep(.el-pagination) {
  flex-wrap: wrap;
  justify-content: center;
}

.form-section {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #ebeef5;
}

.form-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 20px;
  padding-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.section-tip {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.section-description {
  font-size: 12px;
  color: #909399;
  margin-bottom: 16px;
  line-height: 1.6;
}

.section-description p {
  margin: 0;
  padding: 0;
}

.form-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.radio-hint {
  display: block;
  width: 100%;
  margin-top: 8px;
  margin-left: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
  text-align: left;
}

.postgis-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: #f4f4f5;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.postgis-notice .el-icon {
  color: #409eff;
  flex-shrink: 0;
}

.postgis-notice a {
  color: #409eff;
  text-decoration: none;
}

.postgis-notice a:hover {
  text-decoration: underline;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.map-layers-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.map-layer-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  transition: background-color 0.2s;
  cursor: grab;
}

.map-layer-item:active {
  cursor: grabbing;
}

.map-layer-item:hover {
  background: #ecf5ff;
}

.map-layer-item.is-default {
  background: #f0f9ff;
  border: 1px solid #b3d8ff;
}

/* 主行布局（桌面端） */
.map-layer-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.layer-info {
  flex: 1;
  min-width: 0;
}

.layer-info :deep(.el-radio) {
  margin: 0;
}

.layer-info :deep(.el-radio__label) {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.layer-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.layer-id {
  font-size: 12px;
  color: #909399;
}

.layer-status {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

/* 配置输入框区域 */
.map-layer-config {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 30px;
}

.config-input {
  flex: 1;
  min-width: 200px;
}

/* 拖拽手柄 */
.drag-handle {
  cursor: grab;
  color: #909399;
  font-size: 18px;
  flex-shrink: 0;
}

.drag-handle:active {
  cursor: grabbing;
}

/* 移动端排序按钮 */
.mobile-sort-buttons {
  display: none;
  flex-direction: column;
  gap: 2px;
  flex-shrink: 0;
}

.mobile-sort-buttons .el-button {
  padding: 4px;
}

/* vuedraggable 拖拽时的样式 */
.map-layers-list :deep(.sortable-ghost) {
  opacity: 0.5;
  background: #ecf5ff;
}

.map-layers-list :deep(.sortable-drag) {
  opacity: 0.8;
}

/* 默认隐藏桌面端专用元素 */
.desktop-only {
  display: none;
}

/* 默认显示移动端专用元素 */
.mobile-only {
  display: inline;
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .admin-container {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    overflow: hidden;
    background: #f5f7fa;
    width: 100vw;
  }

  .admin-container > .el-container {
    height: 100%;
    width: 100%;
  }

  .el-header {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 100;
    width: 100%;
    overflow: hidden;
  }

  .main {
    padding-top: 70px;
    padding-bottom: 0;
    padding-left: 0;
    padding-right: 0;
    width: 100%;
    box-sizing: border-box;
  }

  .main > .el-tabs {
    width: 100%;
    overflow-x: hidden;
  }

  .header-content h1 {
    font-size: 16px;
    min-width: 0;
  }

  /* 筛选卡片移动端样式 */
  .filter-card {
    margin-bottom: 8px;
  }

  /* 搜索框和按钮之间的间距 */
  .filter-card .el-row .el-col:nth-child(2),
  .filter-card .el-row .el-col:nth-child(3) {
    margin-top: 8px;
  }

  /* Popover 筛选移动端样式 */
  .filter-popover-content {
    padding: 4px 0;
  }

  .filter-section {
    padding: 4px 8px;
  }

  .filter-section .filter-label {
    font-size: 13px;
  }

  .filter-actions {
    padding: 4px 8px;
  }

  .filter-card :deep(.el-card__body) {
    padding: 8px;
  }

  .sort-buttons {
    gap: 4px;
    flex-wrap: nowrap;
  }

  .sort-buttons .el-button {
    font-size: 11px;
    padding: 5px 8px;
  }

  /* 隐藏 PC 端表格，显示移动端卡片 */
  .pc-table {
    display: none !important;
  }

  .mobile-card-list {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 10px;
    /* 为固定底部的分页器留出空间 */
    padding-bottom: 70px;
  }

  /* 移动端列表卡片 */
  .list-card {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
    margin: 0;
    border: none;
    box-shadow: none;
    background: transparent;
  }

  .list-card :deep(.el-card__body) {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
    padding: 0;
  }

  /* 分页器固定在底部 */
  .pagination {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 100;
    background: #f5f7fa;
    padding: 10px;
    padding-bottom: max(10px, env(safe-area-inset-bottom));
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
    margin-top: 0;
    overflow: hidden;
  }

  .pagination :deep(.el-pagination) {
    justify-content: center;
  }

  /* 系统配置 tab 可滚动 */
  .config-tab-content {
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 10px;
  }

  /* 表单项上下布局 */
  :deep(.config-form .el-form-item) {
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-start !important;
  }

  :deep(.config-form .el-form-item__label-wrap) {
    margin-left: 0 !important;
  }

  :deep(.config-form .el-form-item__label) {
    width: auto !important;
    min-width: auto !important;
    text-align: left !important;
    margin-bottom: 8px;
    flex-shrink: 0;
    justify-content: flex-start !important;
  }

  :deep(.config-form .el-form-item__content) {
    margin-left: 0 !important;
    width: 100% !important;
    text-align: left !important;
  }

  /* 地图设置区域移动端优化 */
  .map-layer-config {
    padding-left: 0;
    flex-direction: column;
  }

  .config-input {
    min-width: 100%;
  }

  .map-layer-main {
    flex-wrap: nowrap;
    align-items: flex-start;
  }

  .layer-info {
    flex: 1;
    min-width: 0;
    margin: 0;
    padding: 0;
  }

  .layer-info :deep(.el-radio) {
    align-items: center;
    height: 32px;
    display: inline-flex;
    margin: 0 !important;
  }

  .layer-info :deep(.el-radio__input) {
    margin: 0;
  }

  .layer-info :deep(.el-radio__label) {
    align-items: center;
    line-height: 32px;
    padding-left: 8px;
    margin: 0 !important;
  }

  /* 移动端隐藏拖拽手柄，显示排序按钮 */
  .drag-handle {
    display: none;
  }

  .mobile-sort-buttons {
    display: flex;
    height: 32px;
  }

  .mobile-sort-buttons :deep(.el-button) {
    margin: 0;
  }

  .map-layer-main :deep(.el-switch) {
    flex-shrink: 0;
    align-self: center;
    height: 32px;
  }

  /* 全局重置移动端单选框 margin-right */
  :deep(.el-radio) {
    margin-right: 0 !important;
  }

  .layer-status {
    flex-shrink: 0;
    align-self: center;
  }

  /* 地理编码设置 - 单选按钮垂直排列 */
  :deep(.el-radio-group) {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }

  /* 表格隐藏，使用移动端卡片列表 */
  .el-table {
    display: none;
  }

  /* 移动端卡片列表样式 */
  .mobile-card-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .mobile-user-card,
  .mobile-invite-card {
    background: white;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .mobile-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid #ebeef5;
  }

  .mobile-card-title {
    font-weight: 500;
    font-size: 16px;
    color: #303133;
  }

  .mobile-card-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 14px;
  }

  .mobile-card-row {
    display: flex;
    justify-content: space-between;
  }

  .mobile-card-label {
    color: #909399;
  }

  .mobile-card-value {
    color: #303133;
    text-align: right;
  }

  .mobile-card-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #ebeef5;
  }

  .mobile-card-actions .el-button {
    flex: 1;
  }

  /* 邀请码卡片特殊样式 */
  .invite-code-display {
    font-family: monospace;
    font-size: 16px;
    background: #f5f7fa;
    padding: 8px 12px;
    border-radius: 4px;
  }
}

/* 桌面端隐藏移动端卡片 */
@media (min-width: 1367px) {
  .mobile-card-list {
    display: none !important;
  }

  .pc-table {
    display: table !important;
  }

  .desktop-only {
    display: inline;
  }

  .mobile-only {
    display: none;
  }

  .pagination {
    position: static;
    box-shadow: none;
    padding: 12px 0;
  }
}

/* 字体选择器样式 */
.font-selector-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.font-selector-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.font-selector-desc {
  font-size: 12px;
  color: #909399;
  margin-top: -4px;
  margin-bottom: 4px;
}

@media (max-width: 1366px) {
  .font-selector-item {
    margin-bottom: 12px;
  }

  /* 对话框移动端样式 */
  .responsive-dialog {
    width: 95% !important;
  }

  .responsive-dialog .el-dialog__body {
    max-height: 60vh;
    overflow-y: auto;
  }

  .dialog-form :deep(.el-form-item__label) {
    width: 80px !important;
    font-size: 14px;
  }
}

/* 骨架屏样式 */
.config-skeleton {
  padding: 20px;
}

.list-skeleton {
  padding: 20px;
}

.fonts-skeleton {
  padding: 20px;
}

/* 未保存更改对话框样式 */
.unsaved-changes-dialog .dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.unsaved-changes-dialog p {
  margin: 0;
  font-size: 14px;
  color: #606266;
}
</style>
